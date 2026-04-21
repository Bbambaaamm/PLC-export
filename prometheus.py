# =====================================================================
# Soubor   : prometheus.py
# Účel     : /metrics endpoint (Flask) + sdílené struktury + thread-safety
# Autor    : Michal
# Poznámka : Tento soubor:
#            - drží sdílené struktury pro PLC reader a Flask
#            - exportuje metriky pro Prometheus
#            - používá lock kvůli souběhu PLC vlákna a /metrics requestů
# =====================================================================

from flask import Flask, Response
import collections
import threading
import logging
import time
import pandas as pd

app = Flask(__name__)
log = logging.getLogger("prometheus")

# 🔒 Lock pro sdílené struktury (PLC vlákno + Flask requesty)
last_data_lock = threading.Lock()

# 📡 Uchování posledních hodnot a průjezdů
last_data = {
    # Smartlog základ
    "dnes_pocet_boxu": 0,
    "smartlog_zapnut": 0,
    "vahaChod": 0,

    # Gebhardt pohony
    "M1": 0,
    "M2": 0,

    # Prostoje
    "prostoj1": 0,  # před váhou
    "prostoj2": 0,  # před Ranpak V10
    "prostoj3": 0,  # před Ranpak V20
    "prostoj4": 0,  # před AKL - pravá strana
    "prostoj5": 0,  # před AKL - levá strana
    "prostoj6": 0,  # před pravým teleskopem
    "prostoj7": 0,  # před levým teleskopem

    # BR08 průjezdy
    "br08_prujezdy": collections.deque(maxlen=50),

    # BR08 pomocné diagnostické klíče
    "br08_last_raw": {},
    "br08_ignored_reset_box_id": None,

    # 🚚 Levý teleskop
    "safetyReady_levy_T1": 0,
    "pasChod_levy_T1": 0,

    # 🚚 Pravý teleskop
    "safetyReady_pravy_T2": 0,
    "pasChod_pravy_T2": 0,

    # 🛑 Bezpečnostní tlačítka Gebhardt (ESTOP)
    "aktivovanoTlacitko1": 0,
    "aktivovanoTlacitko2": 0,
    "aktivovanoTlacitko3": 0,
    "aktivovanoTlacitko4": 0,
    "aktivovanoTlacitko5": 0,
    "aktivovanoTlacitko6": 0,

    # 🛑 Bezpečnostní tlačítka Smartlog (ESTOP)
    "aktivovanoTlacitko_ES_TOP1": 0,
    "aktivovanoTlacitko_ES_TOP2": 0,
    "aktivovanoTlacitko_ES_TOP3": 0,
    "aktivovanoTlacitko_ES_TOP4": 0,
    "aktivovanoTlacitko_ES_TOP5": 0,
    "aktivovanoTlacitko_ES_TOP6": 0,
    "aktivovanoTlacitko_ES_TOP7": 0,
    "aktivovanoTlacitko_ES_TOP8": 0,
    "aktivovanoTlacitko_ES_TOP9": 0,
    "aktivovanoTlacitko_ES_TOP10": 0,

    # 🚚 Ranpak V10
    "V10_bReadyToReceiveBox": 0,
    "V10_bReadyToSendBox": 0,
    "V10_bMachineError": 0,
    "V10_bLidSupplyLow": 0,
    "V10_bLidSupplyLowError": 0,
    "V10_bGlueSupplyLowError": 0,
    "V10_safetyReady": 0,

    # 🚚 Ranpak V20
    "V20_bReadyToReceiveBox": 0,
    "V20_bReadyToSendBox": 0,
    "V20_bMachineError": 0,
    "V20_bLidSupplyLow": 0,
    "V20_bLidSupplyLowError": 0,
    "V20_bGlueSupplyLowError": 0,
    "V20_safetyReady": 0,

    # AKL Line1
    "Line1_SystemReady": 0,
    "Line1_StartDispatch": 0,
    "Line1_PassthroughMode": 0,
    "Line1_LabelWarning": 0,
    "Line1_LabelOut": 0,
    "Line1_RibbonWarning": 0,
    "Line1_RibbonOut": 0,

    # AKL Line2
    "Line2_SystemReady": 0,
    "Line2_StartDispatch": 0,
    "Line2_PassthroughMode": 0,
    "Line2_LabelWarning": 0,
    "Line2_LabelOut": 0,
    "Line2_RibbonWarning": 0,
    "Line2_RibbonOut": 0,

    # 📊 Target Počet Boxů - Načítání z Excelu
    "target_pocet_boxu": collections.deque(maxlen=20),

    # 🩺 Exporter/PLC self-observability
    "plc_last_read_timestamp": 0.0,
    "plc_poll_count": 0,
    "plc_read_errors_total": 0,
    "plc_reconnects_total": 0,
    "metrics_scrapes_total": 0,
}

# 🔄 Fronty (sdílené)
# Poznámka:
# Tyto fronty jsou schválně bounded, aby nerostly donekonečna.
pending_metrics = collections.deque(maxlen=500)     # BR08 validní události
pending_prostoje = collections.deque(maxlen=500)    # ukončené prostoje
pending_excel = collections.deque(maxlen=200)       # excel řádky

# 📦 BR08 prefix countery
# Slouží pro přesné počítání validních průjezdů podle prefixu box_id
# a následné použití v PromQL přes increase(...)
br08_prefix_counters = {
    "05": 0,
    "10": 0,
    "15": 0,
    "20": 0,
}

# Bounded “processed dates” – aby to nerostlo donekonečna
_processed_dates_set = set()
_processed_dates_fifo = collections.deque(maxlen=400)
_processed_br08_set = set()
_processed_br08_fifo = collections.deque(maxlen=5000)
_processed_prostoje_set = set()
_processed_prostoje_fifo = collections.deque(maxlen=3000)

# 📊 Nízkokardinalitní agregace pro dashboard/KPI
line_kpis = {
    "br08_events_total": 0,
    "prostoje_events_total": 0,
    "prostoje_duration_seconds_total": 0,
}
br08_response_counters = collections.Counter()
br08_direction_counters = collections.Counter()
prostoje_type_counters = collections.Counter()
prostoje_station_counters = collections.Counter()


def _escape_label_value(v) -> str:
    """
    Prometheus text format:
    label value musí escapovat backslash, quotes a newlines.
    """
    s = "" if v is None else str(v)
    s = s.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
    return s


@app.route("/metrics")
def metrics():
    """
    📡 Vrátí hodnoty pro Prometheus.

    Poznámka:
    - čte last_data pod lockem
    - endpoint je co nejvíce nedestruktivní
    - dočasné snapshoty se používají proto, aby se data během renderu neměnila
    """
    lines = []
    scrape_started = time.time()

    with last_data_lock:
        last_data["metrics_scrapes_total"] += 1
        # snapshoty sdílených struktur
        pending_prostoje_snapshot = list(pending_prostoje)
        pending_metrics_snapshot = list(pending_metrics)
        br08_prefix_counters_snapshot = dict(br08_prefix_counters)

        # 📊 Excel targety – doplnění jen nových datumů
        for datum, prognosa in last_data["target_pocet_boxu"]:
            if datum not in _processed_dates_set:
                pending_excel.append({"datum": datum, "prognosa": prognosa})
                _processed_dates_set.add(datum)
                _processed_dates_fifo.append(datum)

        # evikce ze setu
        while len(_processed_dates_set) > _processed_dates_fifo.maxlen:
            old = _processed_dates_fifo.popleft()
            _processed_dates_set.discard(old)

        pending_excel_snapshot = list(pending_excel)

        # -----------------------------------------------------------------
        # ✅ Nízkokardinalitní KPI agregace z eventů
        # -----------------------------------------------------------------
        for entry in pending_metrics_snapshot:
            event_key = (
                entry.get("box_id"),
                int(entry.get("timestamp", 0)),
                int(entry.get("kod_odpovedi", 0)),
                int(entry.get("smer_vytrideni", 0)),
            )
            if event_key in _processed_br08_set:
                continue

            _processed_br08_set.add(event_key)
            _processed_br08_fifo.append(event_key)
            line_kpis["br08_events_total"] += 1

            br08_response_counters[str(event_key[2])] += 1
            br08_direction_counters[str(event_key[3])] += 1

        while len(_processed_br08_set) > _processed_br08_fifo.maxlen:
            old = _processed_br08_fifo.popleft()
            _processed_br08_set.discard(old)

        for entry in pending_prostoje_snapshot:
            event_key = (
                entry.get("prostoj"),
                int(entry.get("start_timestamp", 0)),
                int(entry.get("end_timestamp", 0)),
                entry.get("type"),
                int(entry.get("duration", 0)),
            )
            if event_key in _processed_prostoje_set:
                continue

            _processed_prostoje_set.add(event_key)
            _processed_prostoje_fifo.append(event_key)
            line_kpis["prostoje_events_total"] += 1
            line_kpis["prostoje_duration_seconds_total"] += max(event_key[4], 0)
            prostoje_type_counters[str(event_key[3])] += 1
            prostoje_station_counters[str(event_key[0])] += 1

        while len(_processed_prostoje_set) > _processed_prostoje_fifo.maxlen:
            old = _processed_prostoje_fifo.popleft()
            _processed_prostoje_set.discard(old)

        # -----------------------------------------------------------------
        # ✅ KPI snapshoty pro line dashboard
        # -----------------------------------------------------------------
        machine_state_keys = [
            "smartlog_zapnut",
            "vahaChod",
            "M1",
            "M2",
            "safetyReady_levy_T1",
            "safetyReady_pravy_T2",
            "V10_safetyReady",
            "V20_safetyReady",
            "Line1_SystemReady",
            "Line2_SystemReady",
        ]
        machines_ready = sum(int(bool(last_data.get(k, 0))) for k in machine_state_keys)
        machines_total = len(machine_state_keys)
        machines_ready_ratio = (machines_ready / machines_total) if machines_total else 0.0

        error_keys = [
            "V10_bMachineError",
            "V10_bLidSupplyLowError",
            "V10_bGlueSupplyLowError",
            "V20_bMachineError",
            "V20_bLidSupplyLowError",
            "V20_bGlueSupplyLowError",
            "Line1_LabelOut",
            "Line1_RibbonOut",
            "Line2_LabelOut",
            "Line2_RibbonOut",
        ]
        active_error_count = sum(int(bool(last_data.get(k, 0))) for k in error_keys)

        latest_target = None
        for entry in pending_excel_snapshot:
            value = entry.get("prognosa")
            if value is not None:
                latest_target = value

        throughput_target_gap = (
            float(last_data["dnes_pocet_boxu"] - latest_target)
            if latest_target is not None
            else 0.0
        )
        now_ts = time.time()
        plc_last_read_ts = float(last_data.get("plc_last_read_timestamp", 0.0) or 0.0)
        plc_data_staleness_seconds = (
            max(0.0, now_ts - plc_last_read_ts) if plc_last_read_ts > 0 else -1.0
        )

        # -----------------------------------------------------------------
        # ✅ Základní gauge metriky
        # -----------------------------------------------------------------
        lines += [
            "# HELP dnes_pocet_boxu Počet boxů dnes",
            "# TYPE dnes_pocet_boxu gauge",
            f"dnes_pocet_boxu {last_data['dnes_pocet_boxu']}",
            "",
        ]

        lines += [
            "# HELP smartlog_zapnut Indikuje, zda je dopravník zapnut",
            "# TYPE smartlog_zapnut gauge",
            f"smartlog_zapnut {last_data['smartlog_zapnut']}",
            "",
        ]

        lines += [
            "# HELP vahaChod Indikuje, zda je váha zapnutá",
            "# TYPE vahaChod gauge",
            f"vahaChod {last_data['vahaChod']}",
            "",
        ]

        # -----------------------------------------------------------------
        # ✅ Teleskopy
        # -----------------------------------------------------------------
        lines += [
            "# HELP safetyReady_levy_T1 Indikuje připravenost levého teleskopu",
            "# TYPE safetyReady_levy_T1 gauge",
            f"safetyReady_levy_T1 {last_data['safetyReady_levy_T1']}",
            "",
            "# HELP pasChod_levy_T1 Indikuje pasový chod levého teleskopu",
            "# TYPE pasChod_levy_T1 gauge",
            f"pasChod_levy_T1 {last_data['pasChod_levy_T1']}",
            "",
            "# HELP safetyReady_pravy_T2 Indikuje připravenost pravého teleskopu",
            "# TYPE safetyReady_pravy_T2 gauge",
            f"safetyReady_pravy_T2 {last_data['safetyReady_pravy_T2']}",
            "",
            "# HELP pasChod_pravy_T2 Indikuje pasový chod pravého teleskopu",
            "# TYPE pasChod_pravy_T2 gauge",
            f"pasChod_pravy_T2 {last_data['pasChod_pravy_T2']}",
            "",
        ]

        # -----------------------------------------------------------------
        # ✅ Pohony
        # -----------------------------------------------------------------
        lines += [
            "# HELP M1 Indikuje stav pohonu M1",
            "# TYPE M1 gauge",
            f"M1 {last_data['M1']}",
            "",
            "# HELP M2 Indikuje stav pohonu M2",
            "# TYPE M2 gauge",
            f"M2 {last_data['M2']}",
            "",
        ]

        # -----------------------------------------------------------------
        # ✅ Bezpečnostní tlačítka Gebhardt
        # -----------------------------------------------------------------
        for i in range(1, 7):
            k = f"aktivovanoTlacitko{i}"
            lines += [
                f"# HELP {k} Indikuje stav bezpečnostního tlačítka {i}",
                f"# TYPE {k} gauge",
                f"{k} {last_data[k]}",
                "",
            ]

        # -----------------------------------------------------------------
        # ✅ Bezpečnostní tlačítka Smartlog
        # -----------------------------------------------------------------
        for i in range(1, 11):
            k = f"aktivovanoTlacitko_ES_TOP{i}"
            lines += [
                f"# HELP {k} Indikuje stav bezpečnostního tlačítka {i}",
                f"# TYPE {k} gauge",
                f"{k} {last_data[k]}",
                "",
            ]

        # -----------------------------------------------------------------
        # ✅ Ranpak + AKL
        # -----------------------------------------------------------------
        simple_keys = [
            "V10_bReadyToReceiveBox", "V10_bReadyToSendBox", "V10_bMachineError",
            "V10_bLidSupplyLow", "V10_bLidSupplyLowError", "V10_bGlueSupplyLowError", "V10_safetyReady",
            "V20_bReadyToReceiveBox", "V20_bReadyToSendBox", "V20_bMachineError",
            "V20_bLidSupplyLow", "V20_bLidSupplyLowError", "V20_bGlueSupplyLowError", "V20_safetyReady",
            "Line1_SystemReady", "Line1_StartDispatch", "Line1_PassthroughMode",
            "Line1_LabelWarning", "Line1_LabelOut", "Line1_RibbonWarning", "Line1_RibbonOut",
            "Line2_SystemReady", "Line2_StartDispatch", "Line2_PassthroughMode",
            "Line2_LabelWarning", "Line2_LabelOut", "Line2_RibbonWarning", "Line2_RibbonOut",
        ]

        for k in simple_keys:
            lines += [
                f"# HELP {k} PLC stav {k}",
                f"# TYPE {k} gauge",
                f"{k} {last_data[k]}",
                "",
            ]

        # -----------------------------------------------------------------
        # ✅ Prostoje – event export
        # Poznámka:
        # Tohle zachovává původní chování.
        # Pro čistě produkční Prometheus model je lepší časem převést
        # na agregované countery/histogramy.
        # -----------------------------------------------------------------
        lines += [
            "# HELP prostoje_info Prostoje se startem, koncem a délkou",
            "# TYPE prostoje_info gauge",
        ]
        for entry in pending_prostoje_snapshot:
            prostoj = _escape_label_value(entry.get("prostoj"))
            st = _escape_label_value(entry.get("start_timestamp"))
            et = _escape_label_value(entry.get("end_timestamp"))
            typ = _escape_label_value(entry.get("type"))
            dur = int(entry.get("duration", 0))
            lines.append(
                f'prostoje_info{{prostoj="{prostoj}", start_timestamp="{st}", end_timestamp="{et}", type="{typ}"}} {dur}'
            )
        lines.append("")

        # -----------------------------------------------------------------
        # ✅ BR08 – event export
        # Poznámka:
        # Zachován původní význam.
        # Pokud bude časem problém s cardinalitou, předělá se na agregaci.
        # -----------------------------------------------------------------
        lines += [
            "# HELP br08_info BR08 průjezdy",
            "# TYPE br08_info gauge",
        ]
        for entry in pending_metrics_snapshot:
            box_id = _escape_label_value(entry.get("box_id"))
            ts = _escape_label_value(entry.get("timestamp"))
            kod = _escape_label_value(entry.get("kod_odpovedi", ""))
            smer = _escape_label_value(entry.get("smer_vytrideni", ""))
            lines.append(
                f'br08_info{{box_id="{box_id}", timestamp="{ts}", kod_odpovedi="{kod}", smer_vytrideni="{smer}"}} 1'
            )
        lines.append("")

        # -----------------------------------------------------------------
        # ✅ BR08 prefix countery
        # Slouží pro přesné počítání boxů podle prefixu přes increase(...)
        # Např.:
        # increase(br08_prefix_total{prefix="10"}[1h])
        # -----------------------------------------------------------------
        lines += [
            "# HELP br08_prefix_total Počet BR08 průjezdů podle prefixu box_id",
            "# TYPE br08_prefix_total counter",
        ]
        for prefix, value in br08_prefix_counters_snapshot.items():
            lines.append(f'br08_prefix_total{{prefix="{prefix}"}} {value}')
        lines.append("")

        # -----------------------------------------------------------------
        # ✅ KPI metriky pro top-level dashboard (nízká kardinalita)
        # -----------------------------------------------------------------
        lines += [
            "# HELP line_br08_events_total Celkový počet BR08 událostí",
            "# TYPE line_br08_events_total counter",
            f"line_br08_events_total {line_kpis['br08_events_total']}",
            "",
            "# HELP line_prostoje_events_total Celkový počet ukončených prostojů",
            "# TYPE line_prostoje_events_total counter",
            f"line_prostoje_events_total {line_kpis['prostoje_events_total']}",
            "",
            "# HELP line_prostoje_duration_seconds_total Celková délka prostojů v sekundách",
            "# TYPE line_prostoje_duration_seconds_total counter",
            f"line_prostoje_duration_seconds_total {line_kpis['prostoje_duration_seconds_total']}",
            "",
            "# HELP line_machines_ready_ratio Podíl strojů v ready/running stavu 0-1",
            "# TYPE line_machines_ready_ratio gauge",
            f"line_machines_ready_ratio {machines_ready_ratio}",
            "",
            "# HELP line_machine_errors_active Počet aktivních error stavů na lince",
            "# TYPE line_machine_errors_active gauge",
            f"line_machine_errors_active {active_error_count}",
            "",
            "# HELP line_throughput_target_gap Rozdíl mezi dnešním počtem boxů a aktuálním targetem",
            "# TYPE line_throughput_target_gap gauge",
            f"line_throughput_target_gap {throughput_target_gap}",
            "",
        ]

        lines += [
            "# HELP plc_last_read_timestamp Unix timestamp posledního úspěšného PLC čtení",
            "# TYPE plc_last_read_timestamp gauge",
            f"plc_last_read_timestamp {plc_last_read_ts}",
            "",
            "# HELP plc_data_staleness_seconds Stáří posledních PLC dat v sekundách; -1 znamená dosud bez čtení",
            "# TYPE plc_data_staleness_seconds gauge",
            f"plc_data_staleness_seconds {plc_data_staleness_seconds}",
            "",
            "# HELP plc_poll_total Počet úspěšných PLC poll cyklů",
            "# TYPE plc_poll_total counter",
            f"plc_poll_total {int(last_data.get('plc_poll_count', 0))}",
            "",
            "# HELP plc_read_errors_total Počet chyb v PLC čtení",
            "# TYPE plc_read_errors_total counter",
            f"plc_read_errors_total {int(last_data.get('plc_read_errors_total', 0))}",
            "",
            "# HELP plc_reconnects_total Počet PLC reconnect pokusů",
            "# TYPE plc_reconnects_total counter",
            f"plc_reconnects_total {int(last_data.get('plc_reconnects_total', 0))}",
            "",
            "# HELP exporter_metrics_scrapes_total Počet scrape dotazů na /metrics",
            "# TYPE exporter_metrics_scrapes_total counter",
            f"exporter_metrics_scrapes_total {int(last_data.get('metrics_scrapes_total', 0))}",
            "",
            "# HELP exporter_pending_queue_fill_ratio Zaplnění interních front 0-1",
            "# TYPE exporter_pending_queue_fill_ratio gauge",
            f'exporter_pending_queue_fill_ratio{{queue="pending_metrics"}} {len(pending_metrics_snapshot) / pending_metrics.maxlen}',
            f'exporter_pending_queue_fill_ratio{{queue="pending_prostoje"}} {len(pending_prostoje_snapshot) / pending_prostoje.maxlen}',
            f'exporter_pending_queue_fill_ratio{{queue="pending_excel"}} {len(pending_excel_snapshot) / pending_excel.maxlen}',
            "",
        ]

        lines += [
            "# HELP line_br08_response_total BR08 odpovědi podle kódu",
            "# TYPE line_br08_response_total counter",
        ]
        for code, value in sorted(br08_response_counters.items()):
            lines.append(f'line_br08_response_total{{kod_odpovedi="{_escape_label_value(code)}"}} {value}')
        lines.append("")

        lines += [
            "# HELP line_br08_direction_total BR08 třídění podle směru",
            "# TYPE line_br08_direction_total counter",
        ]
        for direction, value in sorted(br08_direction_counters.items()):
            lines.append(f'line_br08_direction_total{{smer_vytrideni="{_escape_label_value(direction)}"}} {value}')
        lines.append("")

        lines += [
            "# HELP line_prostoje_type_total Prostoje podle typu",
            "# TYPE line_prostoje_type_total counter",
        ]
        for typ, value in sorted(prostoje_type_counters.items()):
            lines.append(f'line_prostoje_type_total{{type="{_escape_label_value(typ)}"}} {value}')
        lines.append("")

        lines += [
            "# HELP line_prostoje_station_total Prostoje podle části linky",
            "# TYPE line_prostoje_station_total counter",
        ]
        for station, value in sorted(prostoje_station_counters.items()):
            lines.append(f'line_prostoje_station_total{{prostoj="{_escape_label_value(station)}"}} {value}')
        lines.append("")

        # -----------------------------------------------------------------
        # ✅ Target počet boxů z Excelu
        # -----------------------------------------------------------------
        lines += [
            "# HELP target_pocet_boxu Prognóza počtu boxů",
            "# TYPE target_pocet_boxu gauge",
        ]
        for entry in pending_excel_snapshot:
            datum = entry["datum"]
            prognosa = entry["prognosa"]
            ts = pd.to_datetime(datum).timestamp()

            d = _escape_label_value(datum)
            t = _escape_label_value(int(ts))
            lines.append(f'target_pocet_boxu{{datum="{d}", timestamp="{t}"}} {prognosa}')

        lines.append("")

    scrape_duration = max(0.0, time.time() - scrape_started)
    lines += [
        "# HELP exporter_metrics_render_seconds Doba renderu /metrics odpovědi v sekundách",
        "# TYPE exporter_metrics_render_seconds gauge",
        f"exporter_metrics_render_seconds {scrape_duration}",
        "",
    ]

    return Response("\n".join(lines), mimetype="text/plain; version=0.0.4; charset=utf-8")


def start_prometheus():
    """Spustí Flask server pro Prometheus."""
    app.run(host="0.0.0.0", port=8000)
