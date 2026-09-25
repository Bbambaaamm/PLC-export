import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.check_deployment import evaluate, main, parse_metrics, read_source
from db2000 import BR_POSITIONS, ESTOPS, WAITING


def snapshot(tick=0):
    raw = '\n'.join(f'{name} {val}' for name, val in {
        'plc_data_valid': 1, 'plc_data_staleness_seconds': .2,
        'plc_poll_total': 100 + tick, 'plc_last_read_timestamp': 1000 + tick,
        'line_observed_seconds_total': 100 + tick,
        'line_daily_box_count_valid': 1, 'excel_data_valid': 1,
        'excel_active_target_is_today': 1, 'target_pocet_boxu': 2000,
        'event_journal_healthy': 1, 'event_journal_dropped_total': 0,
        'event_journal_errors_total': 0, 'event_journal_pending': 0,
    }.items())
    raw += '\n' + '\n'.join(f'line_br_data_valid{{station="{s}"}} 1' for s in BR_POSITIONS)
    raw += '\n' + '\n'.join(f'br08_prefix_total{{prefix="{p}"}} 100' for p in ('05', '10', '15', '20'))
    for station in WAITING:
        raw += f'\nline_waiting_active{{station="{station}"}} 0\nline_machine_state{{station="{station}"}} 1'
    for estop, byte, bit, _ in ESTOPS:
        raw += f'\nsmartlog_estop_active{{estop="{estop}",address="{byte}.{bit}"}} 0'
    raw += '\nbr08_info{box_id="PRIVATE_BOX",shipping_label="PRIVATE_LABEL"} 1\n'
    return raw


class DeploymentCheckTests(unittest.TestCase):
    def test_healthy_stopped_line_is_not_certified_or_leaked(self):
        first, second = parse_metrics(snapshot()), parse_metrics(snapshot(10))
        # Production can remain constant while a real machine fault/ESTOP is active.
        second['line_machine_state'][0] = (second['line_machine_state'][0][0], 6)
        second['smartlog_estop_active'][0] = (second['smartlog_estop_active'][0][0], 1)
        report = evaluate(first, second)
        self.assertEqual(report['automated_status'], 'passed')
        self.assertEqual(report['acceptance_status'], 'pending_manual_verification')
        self.assertNotIn('PRIVATE', json.dumps(report))
        self.assertNotIn('br08_info', second)

    def test_missing_invalid_and_ambiguous_samples_fail(self):
        for metric in ('plc_data_valid', 'line_br_data_valid', 'event_journal_healthy'):
            for mode in ('missing', 'nan', 'duplicate'):
                with self.subTest(metric=metric, mode=mode):
                    first, second = parse_metrics(snapshot()), parse_metrics(snapshot(10))
                    if mode == 'missing':
                        del second[metric]
                    elif mode == 'nan':
                        second[metric][0] = (second[metric][0][0], float('nan'))
                    else:
                        second[metric].append(second[metric][0])
                    self.assertEqual(evaluate(first, second)['automated_status'], 'failed')

    def test_frozen_polling_restart_and_archive_loss_fail(self):
        changes = [('plc_poll_total', 100), ('plc_poll_total', 0),
                   ('plc_data_staleness_seconds', 30), ('event_journal_dropped_total', 1),
                   ('excel_active_target_is_today', 0), ('br08_prefix_total', 0),
                   ('line_machine_state', -1)]
        for metric, value in changes:
            with self.subTest(metric=metric, value=value):
                first, second = parse_metrics(snapshot()), parse_metrics(snapshot(10))
                second[metric][0] = (second[metric][0][0], value)
                self.assertEqual(evaluate(first, second)['automated_status'], 'failed')

    def test_historical_errors_and_nonempty_queue_warn(self):
        first, second = parse_metrics(snapshot()), parse_metrics(snapshot(10))
        for sample in (first, second):
            sample['event_journal_errors_total'] = [({}, 2)]
        second['event_journal_pending'] = [({}, 3)]
        report = evaluate(first, second)
        self.assertEqual(report['automated_status'], 'passed_with_warnings')
        self.assertEqual(len([c for c in report['checks'] if c['status'] == 'warn']), 2)

    def test_cli_offline_and_failed_fetch_do_not_expose_input(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            first, second, output = [Path(folder) / name for name in ('first.prom', 'second.prom', 'report.json')]
            first.write_text(snapshot())
            second.write_text(snapshot(10))
            self.assertEqual(main(['--first', str(first), '--second', str(second), '--output', str(output)]), 0)
            self.assertNotIn('PRIVATE', output.read_text())
            with patch('scripts.check_deployment.read_source', side_effect=ValueError('secret-token PRIVATE_BOX')):
                self.assertEqual(main(['--metrics-url', 'https://example.invalid/metrics', '--output', str(output)]), 1)
            report = output.read_text()
            self.assertNotIn('secret-token', report)
            self.assertNotIn('PRIVATE_BOX', report)
            self.assertEqual(json.loads(report)['error_type'], 'ValueError')

    def test_no_plaintext_bearer_or_overwritten_snapshot(self):
        with self.assertRaises(ValueError):
            read_source('http://example.invalid/metrics', token='secret')
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()):
            source = Path(folder) / 'first.prom'
            source.write_text(snapshot())
            with self.assertRaises(SystemExit):
                main(['--first', str(source), '--second', str(source), '--output', str(source)])
            self.assertEqual(source.read_text(), snapshot())
