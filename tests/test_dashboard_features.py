import json
from pathlib import Path
import re
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from flask import Flask
from prometheus_client.parser import text_string_to_metric_families
import promql_parser

from db2000 import BR_POSITIONS, ESTOPS, MATERIALS, WAITING, decode_position, s7_string
from eventJournal import EventJournal
from history import history_blueprint
from lineMonitor import LineMonitor, machine_state
from scripts.build_dashboards import build
from smartlog.bezpecnost import read_bezpecnost_smartlog

ROOT = Path(__file__).resolve().parents[1]


def put_string(data, offset, capacity, value):
    payload = value.encode('ascii')
    data[offset:offset + capacity + 2] = bytes([capacity, len(payload)]) + payload + b'X' * (capacity - len(payload))


def buffer():
    data = bytearray(8122)
    for spec in BR_POSITIONS.values():
        put_string(data, spec['box'], 10, '')
        if 'weight' in spec:
            put_string(data, spec['weight'], 7, '')
        if 'shipping' in spec:
            put_string(data, spec['shipping'], 30, '')
    return data


def state():
    result = dict.fromkeys(WAITING.values(), 0)
    result.update({key: 0 for pair in MATERIALS.values() for key in pair if key})
    result.update(dnes_pocet_boxu=0, V10_safetyReady=1, V20_safetyReady=1,
                  safetyReady_levy_T1=1, safetyReady_pravy_T2=1)
    return result


class DatablockTests(unittest.TestCase):
    def test_string_lengths_and_padding(self):
        for length in (0, 1, 8, 10):
            data = bytearray(12)
            put_string(data, 0, 10, '1' * length)
            self.assertEqual(s7_string(data, 0, 10), '1' * length)

    def test_invalid_strings(self):
        for data in (b'\x09\x00' + b' ' * 10, b'\x0a\x0b' + b' ' * 10,
                     b'\x0a\x01\xff' + b' ' * 9, b'\x0a\x01\x00' + b' ' * 9, b'\x0a\x00'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                s7_string(data, 0, 10)

    def test_all_offsets_and_signed_fields(self):
        data = buffer()
        for index, (name, spec) in enumerate(BR_POSITIONS.items()):
            put_string(data, spec['box'], 10, str(10000000 + index))
            data[spec['code']:spec['code'] + 2] = (-200 - index).to_bytes(2, 'big', signed=True)
            if 'direction' in spec:
                data[spec['direction']] = 255
        for index, name in enumerate(BR_POSITIONS):
            record = decode_position(data, name)
            self.assertEqual(record['box_id'], str(10000000 + index))
            self.assertEqual(record['code'], -200 - index)
            self.assertEqual(record['direction'], None if name == 'BR02' else -1)

    def test_estop_one_hot(self):
        for name, byte, bit, _ in ESTOPS:
            data = buffer()
            data[byte] = 1 << bit
            result = {}
            read_bezpecnost_smartlog(data, result)
            self.assertEqual([key for key, value in result['smartlog_estops'].items() if value], [name])


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.monitor = LineMonitor(self.events.append)
        self.data, self.state = buffer(), state()

    def observe(self, mono):
        self.monitor.observe(self.data, self.state, 1700000000 + mono, mono)

    def test_previous_state_duration_and_gap(self):
        self.state['prostoj2'] = 1
        self.observe(0)
        self.state['prostoj2'] = 0
        self.observe(2)
        self.assertEqual(self.monitor.wait_seconds['V10'], 2)
        self.state['prostoj2'] = 1
        self.observe(3)
        self.observe(100)
        self.assertEqual(self.monitor.wait_seconds['V10'], 2)
        self.assertEqual(self.monitor.covered_seconds, 3)
        self.assertEqual(self.monitor.wait_starts['V10'], 100)

    def test_material_lead_warning_can_drop_on_stop(self):
        self.observe(0)
        self.state['Line1_LabelWarning'] = 1
        self.observe(1)
        self.state['Line1_LabelWarning'] = 0
        self.state['Line1_LabelOut'] = 1
        self.observe(4)
        self.assertEqual(self.monitor.warning_leads[('AKL1', 'etikety')], 3)
        self.assertEqual(self.monitor.material_events[('AKL1', 'etikety', 'stop')], 1)

    def test_simultaneous_warning_stop_has_no_lead(self):
        self.observe(0)
        self.state.update(Line1_LabelWarning=1, Line1_LabelOut=1)
        self.observe(1)
        self.assertNotIn(('AKL1', 'etikety'), self.monitor.warning_leads)

    def test_invalid_string_isolated_and_no_duplicate_snapshot(self):
        put_string(self.data, BR_POSITIONS['BR08']['box'], 10, '10000001')
        self.observe(0)
        self.observe(1)
        self.monitor.invalidate()
        self.observe(3)
        self.assertEqual(sum(self.monitor.response_counts.values()), 1)
        self.data[3534] = 0
        self.observe(4)
        self.assertEqual(self.monitor.position_valid['BR08'], 0)
        self.assertEqual(self.monitor.position_valid['BR11'], 1)

    def test_counter_resets_and_negative_values(self):
        for mono, count in enumerate((10, 12, 0, 2, -32768, -32768, 3, 4)):
            self.state['dnes_pocet_boxu'] = count
            self.observe(mono)
        self.assertEqual(self.monitor.box_delta_total, 5)
        self.assertEqual(self.monitor.box_discontinuities, 3)

    def test_readiness_not_running_and_priority(self):
        self.state.update(V10_bReadyToReceiveBox=1)
        self.assertEqual(machine_state('V10', self.state), 1)
        self.state.update(V10_bLidSupplyLowError=1)
        self.assertEqual(machine_state('V10', self.state), 5)
        self.state.update(V10_safetyReady=0)
        self.assertEqual(machine_state('V10', self.state), 7)
        self.state.update(Line1_PassthroughMode=1)
        self.assertEqual(machine_state('AKL1', self.state), 8)

    def test_metrics_parse_unknown_and_no_identifiers(self):
        put_string(self.data, 3534, 10, 'SECRETBOX')
        self.observe(0)
        output = '\n'.join(self.monitor.render(self.state, False, 100)) + '\n'
        self.assertNotIn('SECRETBOX', output)
        self.assertIn('line_machine_state{station="V10"} -1', output)
        self.assertIn('line_br_data_valid{station="BR08"} 0', output)
        self.assertGreater(len(list(text_string_to_metric_families(output))), 10)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'events.sqlite3'
        self.journal = EventJournal(self.path, capacity=2, max_rows=3)

    def event(self, box='10000001', timestamp=None):
        return dict(observed_at=time.time() if timestamp is None else timestamp, kind='br_observation',
                    station='BR08', box_id=box, details={'code': 200})

    def test_freeze_bound_and_restart(self):
        event = self.event()
        self.journal.publish(event)
        event['details']['code'] = 400
        self.journal.publish(self.event())
        self.journal.publish(self.event())
        self.assertEqual(self.journal.health()['dropped_total'], 1)
        self.assertTrue(self.journal.flush_once())
        rows = EventJournal(self.path).search()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['details']['code'], 200)

    def test_failed_write_retries_without_duplicates(self):
        self.journal.publish(self.event())
        with patch('eventJournal.sqlite3.connect', side_effect=sqlite3.OperationalError('disk unavailable')):
            with self.assertLogs('eventJournal', level='WARNING'):
                self.assertFalse(self.journal.flush_once())
        self.assertEqual(self.journal.health()['pending'], 1)
        self.assertTrue(self.journal.flush_once())
        self.assertTrue(self.journal.flush_once())
        self.assertEqual(len(self.journal.search()), 1)

    def test_retention_and_exact_query(self):
        self.journal.publish(self.event(timestamp=time.time() - 8 * 86400))
        self.journal.flush_once()
        self.assertEqual(self.journal.search(since=0), [])
        for index in range(5):
            self.journal.publish(self.event(str(index)))
            self.journal.flush_once()
        self.assertEqual(len(self.journal.search()), 3)
        self.assertEqual(len(self.journal.search(box_id='4')), 1)
        self.assertEqual(self.journal.search(box_id="' OR 1=1 --"), [])

    def test_api_validation_escape_and_missing_archive(self):
        app = Flask(__name__, template_folder=str(ROOT / 'templates'))
        app.register_blueprint(history_blueprint)
        client = app.test_client()
        with patch('history.journal', self.journal):
            self.assertEqual(client.get('/api/events').status_code, 503)
            self.assertFalse(self.path.exists())
            for query in ('limit=201', 'since=nan', 'since=2&until=1', 'since=bad'):
                self.assertEqual(client.get('/api/events?' + query).status_code, 400)
            self.journal.publish(self.event('<script>'))
            self.journal.flush_once()
            result = client.get('/api/events')
            self.assertEqual(result.json['completeness'], 'observations_only')
            self.assertEqual(result.headers['Cache-Control'], 'no-store')
            page = client.get('/history').get_data(as_text=True)
            self.assertNotIn('<script>', page)
            self.assertIn('&lt;script&gt;', page)


class DashboardTests(unittest.TestCase):
    def test_generated_files_and_promql(self):
        for filename, document in build().items():
            self.assertEqual(json.loads((ROOT / 'grafana' / filename).read_text()), document)
            ids = [panel['id'] for panel in document['panels']]
            self.assertEqual(len(ids), len(set(ids)))
            for panel in document['panels']:
                for target in panel.get('targets', []):
                    expression = re.sub(r'\$\{[^}]+\}', lambda m: '3600' if m.group(0) == '${__range_s}' else 'test', target['expr'])
                    with self.subTest(panel=panel['title']):
                        promql_parser.parse(expression)

    def test_alert_expressions(self):
        rules = json.loads((ROOT / 'prometheus_rules' / 'smartlog.rules.yml').read_text())
        for group in rules['groups']:
            for rule in group['rules']:
                promql_parser.parse(rule['expr'])
