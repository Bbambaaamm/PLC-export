"""Generate classic Grafana JSON; no external panel plugins required."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = {"type": "prometheus", "uid": "${DS_PROMETHEUS}"}
S = 'job=~"${job:regex}",instance=~"${instance:regex}"'
STATES = {
    -1: ("Bez platných dat", "gray"), 0: ("Nepřipraveno / bez potvrzení chodu", "gray"),
    1: ("Připraveno", "blue"), 2: ("Chod potvrzen", "green"),
    3: ("Čekání před zařízením", "yellow"), 4: ("Doplňte materiál", "orange"),
    5: ("Materiál došel", "red"), 6: ("Chyba stroje", "red"),
    7: ("Bezpečnost nepřipravena", "red"), 8: ("Průchod bez etiketování", "purple"),
}
NAMES = {"vaha": "Váha", "V10": "Ranpak V10", "V20": "Ranpak V20", "AKL1": "AKL pravá", "AKL2": "AKL levá", "T1": "Teleskop levý", "T2": "Teleskop pravý"}


def selector(name, extra=""):
    return f'{name}{{{S}{"," + extra if extra else ""}}}'


def online(expression):
    return f'({expression}) and on(job,instance) ({selector("up")} == 1)'


def fresh(expression):
    return online(f'({expression}) and on(job,instance) ({selector("plc_data_valid")} == 1)')


def mapping(values):
    return [{"type": "value", "options": {str(k): {"text": v[0], "color": v[1], "index": i} for i, (k, v) in enumerate(values.items())}}]


def panel(pid, title, expr, x, y, w=6, h=5, kind="stat", unit="short", legend="", description="", mappings=None):
    field = {"unit": unit, "noValue": "Bez dat", "color": {"mode": "palette-classic"}, "decimals": 0}
    if mappings:
        field["mappings"] = mapping(mappings)
    options = {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "single"}}
    if kind == "stat":
        options = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "colorMode": "background", "graphMode": "none", "textMode": "auto", "justifyMode": "auto", "orientation": "auto"}
    if kind == "bargauge":
        options = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "displayMode": "gradient", "orientation": "horizontal"}
    if kind == "state-timeline":
        options.update({"mergeValues": True, "showValue": "never", "rowHeight": 0.8})
    return {"id": pid, "title": title, "description": description, "type": kind,
            "gridPos": {"x": x, "y": y, "w": w, "h": h}, "datasource": DS,
            "targets": [{"refId": "A", "expr": expr, "legendFormat": legend,
                         "instant": kind in ("stat", "table", "bargauge"), "range": kind not in ("stat", "table", "bargauge"),
                         "format": "table" if kind == "table" else "time_series", "datasource": DS}],
            "fieldConfig": {"defaults": field, "overrides": []}, "options": options}


def note(pid, title, content, y, h=3):
    return {"id": pid, "title": title, "type": "text", "gridPos": {"x": 0, "y": y, "w": 24, "h": h},
            "options": {"mode": "markdown", "content": content}}


def dashboard(uid, title, panels, detail=False):
    variables = [
        {"name": "DS_PROMETHEUS", "label": "Zdroj dat", "type": "datasource", "query": "prometheus", "refresh": 1},
        {"name": "job", "label": "Exportér", "type": "query", "datasource": DS, "query": "label_values(plc_data_valid, job)", "refresh": 1, "multi": False, "includeAll": False},
        {"name": "instance", "label": "Instance", "type": "query", "datasource": DS, "query": 'label_values(plc_data_valid{job=~"${job:regex}"}, instance)', "refresh": 1, "multi": False, "includeAll": False},
        {"name": "history_url", "label": "Adresa historie", "type": "textbox", "query": "http://EXPORTER:8000/history", "current": {"text": "http://EXPORTER:8000/history", "value": "http://EXPORTER:8000/history"}},
    ]
    if detail:
        variables.append({"name": "station", "label": "Zařízení", "type": "custom", "query": ",".join(NAMES), "current": {"text": "V10", "value": "V10"}, "multi": False, "includeAll": False})
    return {"uid": uid, "title": title, "schemaVersion": 39, "version": 1, "timezone": "Europe/Prague",
            "tags": ["PLC", "DB2000", "Smartlog"], "editable": True, "refresh": "10s", "time": {"from": "now-6h", "to": "now"},
            "templating": {"list": variables}, "panels": panels,
            "links": [{"title": "Dohledat box / incident", "type": "link", "url": "${history_url}", "targetBlank": True},
                      {"title": "Přehled linky" if detail else "Detail zařízení", "type": "link",
                       "url": "/d/plc-line-overview" if detail else "/d/plc-machine-detail", "includeVars": True, "keepTime": True}],
            "annotations": {"list": []}}


def build():
    error_selector = selector("line_br_observations_total", 'result="error"')
    status_map = {-1: ("Bez dat", "gray"), 0: ("Není aktivní", "blue"), 1: ("Aktivní", "orange")}
    panels = [note(1, "SMARTLOG · přehled provozu", "**Pozorované stavy linky** · Čekající box není automaticky porucha. Připravenost Ranpaku nepotvrzuje pracovní cyklus. Neznámé stavy zůstávají šedé. Rozložení karet neurčuje fyzické propojení zařízení.", 0)]
    panels += [panel(2, "Platnost PLC dat", f'{selector("up")} * on(job,instance) {selector("plc_data_valid")}', 0, 3, mappings={0: ("Data nejsou platná", "red"), 1: ("Data aktuální", "green")}),
               panel(3, "Dnes · senzor před vraty 38", fresh(f'{selector("dnes_pocet_boxu")} and on(job,instance) ({selector("line_daily_box_count_valid")} == 1)'), 6, 3),
               panel(4, "Pozorované tempo · boxů/h", fresh(f'rate({selector("line_observed_box_increments_total")}[5m]) * 3600 and on(job,instance) (rate({selector("line_observed_seconds_total")}[5m]) >= 0.9)'), 12, 3, description="Přírůstky PLC počítadla za 5 min. Zobrazeno jen při >=90% časovém pokrytí; nejde o potvrzenou expedici."),
               panel(5, "Plnění dnešního plánu", fresh(f'100 * {selector("dnes_pocet_boxu")} / on(job,instance) ({selector("target_pocet_boxu")} > 0) and on(job,instance) ({selector("excel_active_target_is_today")} == 1) and on(job,instance) ({selector("excel_data_valid")} == 1) and on(job,instance) ({selector("line_daily_box_count_valid")} == 1)'), 18, 3, unit="percent")]
    for i, (station, title) in enumerate(NAMES.items()):
        p = panel(10+i, title, online(selector("line_machine_state", f'station="{station}"')), (i%4)*6, 8+(i//4)*5, mappings=STATES)
        p["fieldConfig"]["defaults"]["links"] = [{"title": "Detail zařízení", "url": f'/d/plc-machine-detail?var-station={station}&var-job=${{job:percentencode}}&var-instance=${{instance:percentencode}}&var-DS_PROMETHEUS=${{DS_PROMETHEUS}}&${{__url_time_range}}'}]
        panels.append(p)
    panels.append(panel(17, "Archiv událostí", online(selector("event_journal_healthy")), 18, 13, mappings={0: ("Archiv nedostupný", "red"), 1: ("Archiv zapisuje", "green")}))
    panels += [panel(20, "Stavy zařízení v čase", online(selector("line_machine_state")), 0, 18, 24, 9, "state-timeline", legend="{{station}}", mappings=STATES),
               panel(21, "Čekání před zařízeními · měřené sekundy", f'increase({selector("line_waiting_seconds_total")}[${{__range_s}}s])', 0, 27, 12, 7, "bargauge", unit="s", legend="{{station}}", description="Součet po stanicích; překryvy nejsou prostojem celé linky. Zahrnuje i čekání kratší než 10 s."),
               panel(22, "Čekání se současným chybovým stavem", fresh(selector("line_waiting_coincidence")), 12, 27, 12, 7, "table", description="Doložený souběh signálů. Neprokazuje kořenovou příčinu."),
               panel(23, "Materiál · varování a zastavení", online(selector("line_material_active")), 0, 34, 12, 9, "state-timeline", legend="{{machine}} · {{material}} · {{level}}", mappings=status_map),
               panel(24, "Poslední změřený čas varování → zastavení", fresh(selector("line_material_warning_lead_seconds")), 12, 34, 12, 9, "bargauge", unit="s", legend="{{machine}} · {{material}}", description="Pouze při zachyceném předchozím varování bez mezery v datech. Lepidlo nemá v DB předběžný warning."),
               panel(25, "Bezpečnostní tlačítka · skutečná označení", online(selector("smartlog_estop_active")), 0, 43, 12, 9, "state-timeline", legend="{{estop}} · {{location}}", mappings=status_map),
               panel(26, "AKL · průchod bez etiketování", online(selector("line_label_bypass_active")), 12, 43, 12, 9, "state-timeline", legend="{{machine}}", mappings={-1: ("Bez dat", "gray"), 0: ("Bypass vypnutý", "blue"), 1: ("Bez etiketování", "purple")}),
               note(30, "ProLag / Plausicheck", "200 = OK; 4xx = chybová odpověď podle dokumentace. Konkrétní důvody vyžadují číselník ProLag. Pozorování BR nejsou garantovanými fyzickými průjezdy. ShippingLabel je dostupný až v historii boxu.", 52),
               panel(31, "BR · aktuální odpovědi", fresh(selector("line_br_response_code")), 0, 55, 8, 7, "table"),
               panel(32, "BR · pozorované chybové odpovědi", f'increase({error_selector}[${{__range_s}}s])', 8, 55, 8, 7, "bargauge", legend="{{station}}"),
               panel(33, "Plausicheck · obsah ShippingLabel", online(selector("line_plausi_label_present")), 16, 55, 8, 7, mappings={-1: ("Bez platných dat", "gray"), 0: ("Řetězec prázdný", "gray"), 1: ("Řetězec vyplněný", "blue")}),
               panel(34, "Kvalita čtení BR", online(selector("line_br_data_valid")), 0, 62, 12, 7, "table"),
               panel(35, "Ztráty při zápisu archivu", selector("event_journal_dropped_total"), 12, 62, 6, 7),
               panel(36, "Reset / nespojitost počítadla", selector("line_box_counter_discontinuities_total"), 18, 62, 6, 7),
               panel(37, "Výkon v čase · pozorované boxy/h", fresh(f'rate({selector("line_observed_box_increments_total")}[5m]) * 3600 and on(job,instance) (rate({selector("line_observed_seconds_total")}[5m]) >= 0.9)'), 0, 69, 24, 8, "timeseries")]
    station = 'station=~"${station:regex}"'
    machine = 'machine=~"${station:regex}"'
    detail = [note(1, "DETAIL · ${station}", "Stav, čekání a materiál ve stejném časovém okně. Prázdný materiálový panel u váhy/teleskopu znamená, že takové signály DB neobsahuje. Historii incidentu otevřete horním odkazem.", 0),
              panel(2, "Aktuální stav", online(selector("line_machine_state", station)), 0, 3, 8, mappings=STATES),
              panel(3, "Aktuální čekání před zařízením", fresh(selector("line_waiting_current_seconds", station)), 8, 3, 8, unit="s"),
              panel(4, "Čekání ve výběru", f'increase({selector("line_waiting_seconds_total", station)}[${{__range_s}}s])', 16, 3, 8, unit="s"),
              panel(5, "Historie stavů", online(selector("line_machine_state", station)), 0, 8, 24, 8, "state-timeline", mappings=STATES),
              panel(6, "Materiálové stavy", online(selector("line_material_active", machine)), 0, 16, 12, 8, "state-timeline", legend="{{material}} · {{level}}", mappings=status_map),
              panel(7, "Souběh čekání a chybového stavu", fresh(selector("line_waiting_coincidence", station)), 12, 16, 12, 8, "table"),
              panel(8, "Čas podle zobrazovaného stavu", f'increase({selector("line_machine_state_seconds_total", station)}[${{__range_s}}s])', 0, 24, 24, 7, "bargauge", unit="s", legend="stav {{state}}", description="Vzájemně výlučné stavy podle zobrazovací priority, nikoli OEE. Neznámé intervaly se nepočítají.")]
    return {"line-overview.json": dashboard("plc-line-overview", "Smartlog · přehled linky", panels),
            "machine-detail.json": dashboard("plc-machine-detail", "Smartlog · detail zařízení", detail, True)}


if __name__ == "__main__":
    for filename, content in build().items():
        (ROOT / "grafana").mkdir(exist_ok=True)
        (ROOT / "grafana" / filename).write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n")
