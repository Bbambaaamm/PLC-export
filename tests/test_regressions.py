import copy
import logging
import unittest
from unittest.mock import Mock, patch

import pandas as pd
from prometheus_client.parser import text_string_to_metric_families

import prometheus as metrics
import plcReader as reader
import excelReader as excel
from config import SIZE, EXCEL_REFRESH_INTERVAL_SEC
from smartlog.br.br08 import read_br08
from smartlog.prostoje import read_prostoje, prostoj_start_time


INITIAL_DATA = copy.deepcopy(metrics.last_data)


class StopLoop(BaseException):
    pass


class ExporterRegressions(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        metrics.last_data.clear()
        metrics.last_data.update(copy.deepcopy(INITIAL_DATA))
        for queue in (metrics.pending_metrics, metrics.pending_prostoje):
            queue.clear()
        for counters in (
            metrics.br08_response_counters, metrics.br08_direction_counters,
            metrics.prostoje_type_counters, metrics.prostoje_station_counters,
            metrics.prostoje_station_duration_counters,
        ):
            counters.clear()
        for counters in (metrics.line_kpis, metrics.br08_prefix_counters):
            for key in counters:
                counters[key] = 0
        prostoj_start_time.clear()
        self.client = metrics.app.test_client()

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def scrape(self):
        response = self.client.get('/metrics')
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        list(text_string_to_metric_families(text))
        return text

    def sample(self, monotonic, wall=1000, error=False, downtime=False):
        data = bytearray(SIZE)
        data[28] = 4 if error else 0
        data[62] = 1 if downtime else 0
        with metrics.last_data_lock:
            reader.process_sample(data, wall, monotonic)

    def test_metrics_without_plc_are_valid_but_not_healthy(self):
        self.assertIn('\nplc_data_valid 0\n', self.scrape())

    def test_revised_and_deleted_excel_rows_replace_previous_plan(self):
        day = pd.Timestamp.now(tz='Europe/Prague').date().isoformat()
        with patch.object(excel, 'read_excel_data'), patch.object(
            excel, 'get_target_pocet_boxu', side_effect=[[(day, 100)], [(day, 250)], []]
        ):
            excel.refresh_excel_targets()
            self.assertIn('\ntarget_pocet_boxu 100.0\n', self.scrape())
            excel.refresh_excel_targets()
            self.assertIn('\ntarget_pocet_boxu 250.0\n', self.scrape())
            excel.refresh_excel_targets()
            self.assertIn('\ntarget_pocet_boxu NaN\n', self.scrape())

    def test_daily_targets_have_correct_names_and_no_explicit_timestamp(self):
        metrics.last_data['target_pocet_boxu'] = [('2026-09-24', 100), ('2026-09-25', 250)]
        text = self.scrape()
        for day, value in metrics.last_data['target_pocet_boxu']:
            name = 'target_pocet_boxu_podle_dne'
            line = next(line for line in text.splitlines() if line.startswith(f'{name}{{datum="{day}"}}'))
            self.assertEqual(line, f'{name}{{datum="{day}"}} {float(value)}')
        samples = [sample for family in text_string_to_metric_families(text)
                   for sample in family.samples if sample.name == 'target_pocet_boxu']
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].labels, {})

    def test_full_year_plan_is_not_truncated_by_event_buffer(self):
        metrics.last_data['target_pocet_boxu'] = [
            (date.date().isoformat(), 100) for date in pd.date_range('2026-01-01', periods=365)
        ]
        text = self.scrape()
        self.assertEqual(sum(line.startswith('target_pocet_boxu_podle_dne{') for line in text.splitlines()), 365)

    def test_excel_failure_retains_plan_and_marks_it_invalid(self):
        metrics.last_data['target_pocet_boxu'] = [('2026-09-25', 100)]
        with patch.object(excel, 'read_excel_data', side_effect=FileNotFoundError):
            excel.refresh_excel_targets()
        self.assertEqual(metrics.last_data['target_pocet_boxu'], [('2026-09-25', 100)])
        self.assertEqual(metrics.last_data['excel_data_valid'], 0)
        self.assertEqual(metrics.last_data['excel_read_errors_total'], 1)

    def test_failed_excel_refresh_waits_full_interval(self):
        with patch.object(excel, 'read_excel_data', side_effect=FileNotFoundError) as read, patch.object(
            excel.time, 'sleep', side_effect=StopLoop
        ) as sleep:
            with self.assertRaises(StopLoop):
                excel.read_excel_targets()
        read.assert_called_once()
        sleep.assert_called_once_with(EXCEL_REFRESH_INTERVAL_SEC)

    def test_short_and_oversized_samples_do_not_publish(self):
        for size in (0, 1, 3650, SIZE - 1, SIZE + 1):
            with self.assertRaises(ValueError):
                reader.process_sample(bytearray(size), 1000, 0)
            self.assertEqual(metrics.last_data['plc_last_read_timestamp'], 0)
            self.assertEqual(metrics.last_data['plc_poll_count'], 0)

    def test_read_loop_invalidates_previous_sample_on_short_read(self):
        self.sample(0, error=True, downtime=True)
        plc = Mock()
        plc.get_connected.return_value = True
        plc.db_read.return_value = bytearray(1)
        with patch.object(reader, 'connect_to_plc', return_value=plc), patch.object(
            reader.time, 'sleep', side_effect=StopLoop
        ), patch.object(excel, 'read_excel_data', side_effect=AssertionError('PLC must not read Excel')) as read:
            with self.assertRaises(StopLoop):
                reader.read_plc_data()
        self.assertEqual(metrics.last_data['plc_data_valid'], 0)
        self.assertEqual(metrics.last_data['plc_poll_count'], 1)
        self.assertEqual(metrics.last_data['plc_read_errors_total'], 1)
        self.assertIsNone(metrics.last_data['errors_last_sample_timestamp'])
        self.assertFalse(prostoj_start_time)
        plc.disconnect.assert_called_once()
        read.assert_not_called()

    def test_time_interval_is_assigned_to_previous_state(self):
        self.sample(0, error=False)
        self.sample(1, error=True)
        self.assertEqual(metrics.last_data['V10_error_active_seconds_total'], 0)
        self.sample(3, error=False)
        self.assertEqual(metrics.last_data['V10_error_active_seconds_total'], 2)

    def test_hour_gap_is_not_counted_as_machine_error(self):
        self.sample(0, error=False)
        self.sample(3600, error=True)
        self.assertEqual(metrics.last_data['V10_error_active_seconds_total'], 0)
        self.sample(3601, error=True)
        self.assertEqual(metrics.last_data['V10_error_active_seconds_total'], 1)

    def test_reconnect_does_not_bridge_downtime(self):
        self.sample(0, error=True, downtime=True)
        with metrics.last_data_lock:
            reader.invalidate_plc_data()
        self.sample(3600, error=False, downtime=False)
        self.assertEqual(metrics.last_data['V10_error_active_seconds_total'], 0)
        self.assertFalse(metrics.pending_prostoje)

    def test_long_poll_pause_discards_interrupted_downtime(self):
        self.sample(0, downtime=True)
        self.sample(3600, downtime=False)
        self.assertFalse(metrics.pending_prostoje)

    def test_wall_clock_jump_does_not_change_duration(self):
        self.sample(0, wall=1000, error=True)
        self.sample(1, wall=100000, error=False)
        self.assertEqual(metrics.last_data['V10_error_active_seconds_total'], 1)

    def test_stalled_reader_health_expires(self):
        self.sample(0, wall=1000)
        with patch.object(metrics.time, 'monotonic', return_value=1):
            self.assertIn('\nplc_data_valid 1\n', self.scrape())
        with patch.object(metrics.time, 'monotonic', return_value=100):
            self.assertIn('\nplc_data_valid 0\n', self.scrape())

    def test_backward_wall_clock_jump_cannot_extend_plc_validity(self):
        self.sample(100, wall=10000)
        with patch.object(metrics.time, 'time', return_value=1000), patch.object(
            metrics.time, 'monotonic', return_value=200
        ):
            text = self.scrape()
        self.assertIn('\nplc_data_valid 0\n', text)
        self.assertIn('\nplc_data_staleness_seconds 100\n', text)
        self.assertIn('\nplc_last_read_timestamp 10000.0\n', text)

    def test_forward_wall_clock_jump_does_not_expire_fresh_data(self):
        self.sample(100, wall=10000)
        with patch.object(metrics.time, 'time', return_value=100000), patch.object(
            metrics.time, 'monotonic', return_value=101
        ):
            self.assertIn('\nplc_data_valid 1\n', self.scrape())

    def test_501_br08_events_count_without_any_scrape(self):
        for i in range(501):
            data = bytearray(SIZE)
            data[3534:3546] = bytes([10, 10]) + f'10{i:08d}'.encode('ascii')
            data[3649] = 1
            data[3650] = 1
            read_br08(data, metrics.last_data, metrics.pending_metrics)
        self.assertEqual(metrics.line_kpis['br08_events_total'], 501)
        self.assertEqual(metrics.br08_prefix_counters['10'], 501)
        self.assertEqual(len(metrics.pending_metrics), 500)
        self.scrape()
        self.scrape()
        self.assertEqual(metrics.line_kpis['br08_events_total'], 501)

    def test_501_downtimes_count_without_any_scrape(self):
        data = bytearray(SIZE)
        for i in range(501):
            data[62] = 1
            read_prostoje(data, metrics.last_data, metrics.pending_prostoje, wall_time=1000 + i * 20, monotonic_time=i * 20)
            data[62] = 0
            read_prostoje(data, metrics.last_data, metrics.pending_prostoje, wall_time=1010 + i * 20, monotonic_time=10 + i * 20)
        self.assertEqual(metrics.line_kpis['prostoje_events_total'], 501)
        self.assertEqual(metrics.line_kpis['prostoje_duration_seconds_total'], 5010)
        self.assertEqual(metrics.prostoje_station_duration_counters['prostoj1'], 5010)
        self.assertEqual(len(metrics.pending_prostoje), 500)
        self.scrape()
        self.scrape()
        self.assertEqual(metrics.line_kpis['prostoje_events_total'], 501)

    def test_cumulative_error_metrics_are_counters(self):
        self.assertIn('# TYPE V10_error_active_seconds_total counter', self.scrape())

    def test_legacy_event_details_can_be_disabled_without_losing_counts(self):
        metrics.record_br08_event(dict(box_id='100000000001', timestamp=1000, kod_odpovedi=1, smer_vytrideni=1))
        with patch.dict('os.environ', {'EXPORT_EVENT_DETAILS': '0'}):
            text = self.scrape()
        self.assertNotIn('\nbr08_info{', text)
        self.assertIn('\nline_br08_events_total 1\n', text)


if __name__ == '__main__':
    unittest.main()
