"""Read-only two-snapshot exporter checks. Does not certify PLC or site acceptance."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from prometheus_client.parser import text_string_to_metric_families

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from db2000 import BR_POSITIONS, ESTOPS, WAITING

MAX_BYTES = 10 * 1024 * 1024
MANUAL_GATES = [
    "Aktuální DB mapa, polarita ESTOP a význam signálů potvrzené technikem (#12, #14).",
    "Heartbeat, sekvence, atomická publikace a buffer událostí potvrzené PLC programátorem (#12).",
    "Topologie, ProLag číselník, hotový box a směnové KPI schválené provozem (#13).",
    "Grafana a Prometheus ověřeny na cílových verzích a reálných datech (#14).",
    "Trvalost SQLite, záloha/obnova, přístup a řízené scénáře doložené protokolem (#14).",
]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_source(source, timeout=5, token=None):
    if source.startswith(('http://', 'https://')):
        parsed = urlsplit(source)
        if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError('Invalid metrics URL')
        if token and parsed.scheme != 'https':
            raise ValueError('Bearer authentication requires HTTPS')
        headers = {'Accept': 'text/plain'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        # A redirect must not forward credentials to a different service.
        with build_opener(NoRedirect()).open(Request(source, headers=headers), timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
    else:
        with Path(source).open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('Metrics response too large')
    return raw.decode('utf-8')


def parse_metrics(raw):
    # Ignore detail series: their labels may contain BoxID or ShippingLabel.
    wanted = {'plc_data_valid', 'plc_data_staleness_seconds', 'plc_poll_total',
              'plc_last_read_timestamp', 'line_br_data_valid', 'br08_prefix_total',
              'line_waiting_active', 'line_machine_state', 'smartlog_estop_active',
              'excel_data_valid', 'excel_active_target_is_today', 'target_pocet_boxu',
              'line_daily_box_count_valid', 'line_observed_seconds_total',
              'event_journal_healthy', 'event_journal_dropped_total',
              'event_journal_errors_total', 'event_journal_pending'}
    result = {}
    for family in text_string_to_metric_families(raw):
        for sample in family.samples:
            if sample.name in wanted:
                result.setdefault(sample.name, []).append((sample.labels, float(sample.value)))
    return result


def value(snapshot, name, labels=None):
    labels = labels or {}
    matches = [v for tags, v in snapshot.get(name, [])
               if all(tags.get(k) == v for k, v in labels.items())]
    if len(matches) != 1 or not math.isfinite(matches[0]):
        raise ValueError('Missing, ambiguous or non-finite metric')
    return matches[0]


def evaluate(first, second, max_age=5):
    if not math.isfinite(max_age) or max_age <= 0:
        raise ValueError('max_age must be finite and positive')
    checks = []

    def check(name, predicate, message):
        try:
            ok = predicate()
        except (ValueError, KeyError):
            ok = False
        checks.append({'check': name, 'status': 'pass' if ok else 'fail', 'meaning': message})

    def both(metric, predicate, labels=None):
        return all(predicate(value(s, metric, labels)) for s in (first, second))

    for metric in ('plc_data_valid', 'line_daily_box_count_valid', 'excel_data_valid',
                   'excel_active_target_is_today', 'event_journal_healthy'):
        check(metric, lambda m=metric: both(m, lambda v: v == 1), 'Platný stav v obou vzorcích.')
    check('plc_freshness', lambda: both('plc_data_staleness_seconds', lambda v: 0 <= v <= max_age),
          'Stáří čtení v nastavené toleranci; není důkaz běhu PLC programu.')
    for metric in ('plc_poll_total', 'plc_last_read_timestamp', 'line_observed_seconds_total'):
        check(metric, lambda m=metric: 0 <= value(first, m) < value(second, m),
              'Hodnota roste mezi vzorky; restart vyžaduje nové měření.')
    check('target_pocet_boxu', lambda: both('target_pocet_boxu', lambda v: v > 0),
          'Kladný denní plán; není schváleným směnovým KPI.')
    for station in BR_POSITIONS:
        check('BR_valid:' + station, lambda s=station: both('line_br_data_valid', lambda v: v == 1, {'station': s}),
              'Platný dekódovaný BR snapshot; nepotvrzuje úplnost průjezdů.')
    for prefix in ('05', '10', '15', '20'):
        labels = {'prefix': prefix}
        check('BR08_prefix:' + prefix,
              lambda ls=labels: 0 <= value(first, 'br08_prefix_total', ls) <= value(second, 'br08_prefix_total', ls),
              'Přítomný neklesající čítač; růst není vyžadován při zastavení.')
    for station in WAITING:
        labels = {'station': station}
        check('waiting:' + station, lambda ls=labels: both('line_waiting_active', lambda v: v in (0, 1), ls),
              'Čekání je dostupné; aktivní čekání není chyba sběru.')
        check('state:' + station, lambda ls=labels: both('line_machine_state', lambda v: v in range(9), ls),
              'Stav je známý; připravenost není potvrzení pracovního cyklu.')
    for estop, byte, bit, _ in ESTOPS:
        labels = {'estop': estop, 'address': f'{byte}.{bit}'}
        check('ESTOP:' + estop, lambda ls=labels: both('smartlog_estop_active', lambda v: v in (0, 1), ls),
              'Identifikátor/adresa přítomné; polaritu a funkci ověřuje technik.')
    for metric in ('event_journal_dropped_total', 'event_journal_errors_total'):
        check(metric, lambda m=metric: 0 <= value(first, m) == value(second, m),
              'Během měření nepřibyly ztráty/chyby a nenastal reset čítače.')
        try:
            if value(second, metric) > 0:
                checks.append({'check': metric + ':history', 'status': 'warn',
                               'meaning': 'V tomto běhu už byly zaznamenány chyby nebo ztráty; vyhodnotit historii.'})
        except ValueError:
            pass
    check('event_journal_pending', lambda: both('event_journal_pending', lambda v: v >= 0),
          'Metrika fronty je dostupná.')
    try:
        if value(second, 'event_journal_pending') > 0:
            checks.append({'check': 'archive_queue', 'status': 'warn',
                           'meaning': 'Fronta při druhém měření nebyla prázdná; krátké měření nepotvrzuje její odtok.'})
    except ValueError:
        pass
    return {'schema_version': 1, 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
            'automated_status': 'failed' if any(c['status'] == 'fail' for c in checks) else
                                'passed_with_warnings' if any(c['status'] == 'warn' for c in checks) else 'passed',
            'acceptance_status': 'pending_manual_verification', 'checks': checks, 'manual_gates': MANUAL_GATES}


def positive_seconds(raw):
    value = float(raw)
    if not math.isfinite(value) or not 0 < value <= 30:
        raise argparse.ArgumentTypeError('Použijte čas větší než 0 a nejvýše 30 sekund.')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metrics-url', help='Přímý /metrics endpoint jedné instance exportéru.')
    parser.add_argument('--first', type=Path, help='První lokální Prometheus text snapshot.')
    parser.add_argument('--second', type=Path, help='Druhý lokální Prometheus text snapshot.')
    parser.add_argument('--interval', type=positive_seconds, default=5)
    parser.add_argument('--timeout', type=positive_seconds, default=5)
    parser.add_argument('--max-age', type=positive_seconds, default=5)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if bool(args.metrics_url) == bool(args.first or args.second) or (not args.metrics_url and not (args.first and args.second)):
        parser.error('Zadejte buď --metrics-url, nebo oba soubory --first a --second.')
    if args.metrics_url and urlsplit(args.metrics_url).scheme not in ('http', 'https'):
        parser.error('--metrics-url musí používat http nebo https.')
    if args.first and args.output.resolve() in {args.first.resolve(), args.second.resolve()}:
        parser.error('Výstup nesmí přepsat vstupní snapshot.')
    try:
        token = os.environ.get('PLC_CHECK_BEARER_TOKEN') if args.metrics_url else None
        first = parse_metrics(read_source(args.metrics_url or str(args.first), args.timeout, token))
        if args.metrics_url:
            time.sleep(args.interval)
        second = parse_metrics(read_source(args.metrics_url or str(args.second), args.timeout, token))
        report = evaluate(first, second, args.max_age)
        report['source_mode'] = 'http_two_samples' if args.metrics_url else 'supplied_snapshots'
    except Exception as exc:
        # Exception text can contain credentials, URLs or raw labels. Never export it.
        report = {'schema_version': 1, 'automated_status': 'failed', 'error_type': type(exc).__name__,
                  'acceptance_status': 'pending_manual_verification', 'manual_gates': MANUAL_GATES}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(report['automated_status'] + '; provozní akceptace vyžaduje ruční protokol.')
    return 1 if report['automated_status'] == 'failed' else 0


if __name__ == '__main__':
    sys.exit(main())
