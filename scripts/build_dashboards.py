"""Generate compact operations dashboards using native Grafana panels."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = {"type": "prometheus", "uid": "${DS_PROMETHEUS}"}
S = 'job=~"${job:regex}",instance=~"${instance:regex}"'
WINDOW = '${__range_s}s'
STATES = {
    -1: ("Bez platných dat", "gray"), 0: ("Bez potvrzení chodu", "gray"),
    1: ("Připraveno", "blue"), 2: ("Chod potvrzen", "green"),
    3: ("Čekání před zařízením", "yellow"), 4: ("Doplňte materiál", "orange"),
    5: ("Materiál došel", "red"), 6: ("Chyba stroje", "red"),
    7: ("Bezpečnost nepřipravena", "red"), 8: ("Průchod bez etiketování", "purple"),
}
NAMES = {"vaha": "Váha", "V10": "Ranpak V10", "V20": "Ranpak V20", "AKL1": "AKL pravá", "AKL2": "AKL levá", "T1": "Teleskop levý", "T2": "Teleskop pravý"}
MATERIAL_NAMES = {"vika": "Víka", "lepidlo": "Lepidlo", "etikety": "Etikety", "paska": "Páska"}
CONDITIONS = {"material_stop": "Nedostatek materiálu", "machine_error": "Chyba stroje", "safety_not_ready": "Bezpečnost nepřipravena", "label_bypass": "Průchod bez etiketování"}
# Public metric, operator label, whether a 1 indicates a problem.
RANPAK_SIGNALS = [("safetyReady", "Bezpečnost", False), ("bReadyToReceiveBox", "Příjem boxu", False),
                  ("bReadyToSendBox", "Výstup boxu", False), ("bMachineError", "Chyba stroje", True),
                  ("bLidSupplyLow", "Víka · varování", True), ("bLidSupplyLowError", "Víka · došla", True),
                  ("bGlueSupplyLowError", "Lepidlo · došlo", True)]
AKL_SIGNALS = [("SystemReady", "Připravenost", False), ("StartDispatch", "Výdej boxu", False),
               ("LabelWarning", "Etikety · varování", True), ("LabelOut", "Etikety · došly", True),
               ("RibbonWarning", "Páska · varování", True), ("RibbonOut", "Páska · došla", True),
               ("PassthroughMode", "Bez etiketování", True)]


def selector(name, extra=""):
    return f'{name}{{{S}{"," + extra if extra else ""}}}'


def online(expression):
    return f'({expression}) and on(job,instance) ({selector("up")} == 1)'


def fresh(expression):
    return online(f'({expression}) and on(job,instance) ({selector("plc_data_valid")} == 1)')


def increase(name, extra=""):
    return f'increase({selector(name, extra)}[{WINDOW}])'


def mapping(values):
    return [{"type": "value", "options": {str(k): {"text": v[0], "color": v[1], "index": i} for i, (k, v) in enumerate(values.items())}}]


def override(name, **properties):
    return {"matcher": {"id": "byName", "options": name}, "properties": [{"id": k, "value": v} for k, v in properties.items()]}


def panel(pid, title, expr, x, y, w=6, h=4, kind="stat", unit="none", legend="", description="", mappings=None, color="blue"):
    instant = kind in ("stat", "table", "bargauge", "gauge")
    field = {"unit": unit, "noValue": "Bez dat", "color": {"mode": "fixed", "fixedColor": color}, "decimals": 0}
    if mappings:
        field["mappings"] = mapping(mappings)
    options = {"legend": {"displayMode": "list", "placement": "bottom", "calcs": []}, "tooltip": {"mode": "multi", "sort": "desc"}}
    if kind == "stat":
        options = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "colorMode": "value", "graphMode": "none", "textMode": "auto", "justifyMode": "center", "orientation": "auto", "text": {"titleSize": 12, "valueSize": 26}}
    if kind in ("bargauge", "gauge"):
        options = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "displayMode": "basic", "orientation": "horizontal", "showUnfilled": True, "valueMode": "color", "namePlacement": "left", "minVizHeight": 14, "minVizWidth": 0, "text": {"titleSize": 11, "valueSize": 12}}
    if kind == "state-timeline":
        field["color"] = {"mode": "palette-classic"}
        options.update({"mergeValues": True, "showValue": "never", "rowHeight": 0.75, "alignValue": "left"})
        options["legend"]["showLegend"] = False
        field["custom"] = {"lineWidth": 0, "fillOpacity": 85, "spanNulls": False, "insertNulls": True}
    if kind == "timeseries":
        field["color"] = {"mode": "palette-classic"}
        field["custom"] = {"drawStyle": "line", "lineInterpolation": "linear", "lineWidth": 1, "fillOpacity": 10, "showPoints": "never", "spanNulls": False, "axisLabel": "%" if unit == "percent" else "boxů/h", "axisBorderShow": False}
    return {"id": pid, "title": title, "description": description, "type": kind,
            "gridPos": {"x": x, "y": y, "w": w, "h": h}, "datasource": DS,
            "targets": [{"refId": "A", "expr": expr, "legendFormat": legend, "instant": instant, "range": not instant,
                         "format": "table" if kind == "table" else "time_series", "datasource": DS}],
            "fieldConfig": {"defaults": field, "overrides": []}, "options": options}


def row(pid, title, y):
    return {"id": pid, "type": "row", "title": title, "collapsed": False, "panels": [], "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}}


def unavailable(pid, title, reason, x, y, w):
    # A deliberately empty vector: an undefined KPI must never appear as zero.
    p = panel(pid, title, "vector(0) unless vector(0)", x, y, w, 3, description=reason, color="text")
    p["fieldConfig"]["defaults"]["noValue"] = "Není definováno"
    p["options"]["text"]["valueSize"] = 16
    return p


def station_names(p):
    p["fieldConfig"]["overrides"] += [override(key, displayName=value) for key, value in NAMES.items()]
    return p


def signal_board(pid, title, signals, x, y, w=3, h=8):
    p = panel(pid, title, "", x, y, w, h, "bargauge", description="Aktuální signály DB. Zelená = aktivní provozní signál nebo neaktivní chyba; červená = aktivní chyba, oranžová = varování. Bez platných dat se signály nezobrazují jako zdravé.")
    p["targets"] = []
    p["options"].update(displayMode="basic", namePlacement="top")
    p["fieldConfig"]["defaults"].update(min=0, max=1)
    for i, (metric, label, bad) in enumerate(signals):
        p["targets"].append({"refId": chr(65+i), "expr": fresh(selector(metric)), "legendFormat": label,
                             "instant": True, "range": False, "datasource": DS})
        one_color = "orange" if "varování" in label else "purple" if "etiketování" in label else "red" if bad else "green"
        zero_color = "green" if bad else "gray"
        p["fieldConfig"]["overrides"].append(override(label, mappings=mapping({0: ("Ne", zero_color), 1: ("Ano", one_color)}),
            color={"mode": "thresholds"}, thresholds={"mode": "absolute", "steps": [{"color": zero_color, "value": None}, {"color": one_color, "value": 1}]}))
    return p


def estop_board(pid, title, metric, legend, x, y, w=3, h=8):
    p = panel(pid, title, fresh(selector(metric)), x, y, w, h, "bargauge", legend=legend,
              mappings={0: ("Neaktivní", "green"), 1: ("Aktivní", "red")})
    p["options"].update(displayMode="basic", namePlacement="top")
    p["fieldConfig"]["defaults"].update(min=0, max=1, color={"mode": "thresholds"}, thresholds={"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "red", "value": 1}]})
    return p


def clean_table(p, columns, names=None):
    # The Prometheus table response contains job/instance/__name__/Time; keep only operator fields.
    keep = set(columns)
    all_fields = {"Time", "__name__", "job", "instance", "station", "machine", "material", "level", "condition", "Value", "address", "location", "estop"}
    p["transformations"] = [{"id": "organize", "options": {"excludeByName": {k: True for k in sorted(all_fields - keep)},
        "indexByName": {k: i for i, k in enumerate(columns)}, "renameByName": names or {}}}]
    p["options"] = {"showHeader": True, "cellHeight": "sm", "footer": {"show": False}}
    return p


def dashboard(uid, title, panels, detail=False):
    variables = [
        {"name": "DS_PROMETHEUS", "label": "Zdroj", "type": "datasource", "query": "prometheus", "refresh": 1},
        {"name": "job", "label": "Exportér", "type": "query", "datasource": DS, "query": "label_values(plc_data_valid, job)", "refresh": 1, "multi": False, "includeAll": False},
        {"name": "instance", "label": "Instance", "type": "query", "datasource": DS, "query": 'label_values(plc_data_valid{job=~"${job:regex}"}, instance)', "refresh": 1, "multi": False, "includeAll": False},
        {"name": "history_url", "label": "Adresa historie", "type": "textbox", "hide": 2, "query": "http://EXPORTER:8000/history", "current": {"text": "http://EXPORTER:8000/history", "value": "http://EXPORTER:8000/history"}},
    ]
    if detail:
        variables.append({"name": "station", "label": "Zařízení", "type": "custom", "query": ",".join(NAMES), "current": {"text": "V10", "value": "V10"}, "multi": False, "includeAll": False})
    return {"uid": uid, "title": title, "schemaVersion": 39, "version": 2, "timezone": "Europe/Prague",
            "description": "Kompaktní provozní přehled podle původního dashboardu. Čekání není automaticky porucha; BR pozorování nejsou garantované průjezdy. OEE a forecast vyžadují schválený kontrakt a směnový kalendář.",
            "tags": ["PLC", "DB2000", "Smartlog"], "editable": True, "refresh": "10s", "time": {"from": "now-6h", "to": "now"},
            "templating": {"list": variables}, "panels": panels, "graphTooltip": 1,
            "links": [{"title": "Historie boxů / incidentů", "type": "link", "url": "${history_url}", "targetBlank": True},
                      {"title": "Přehled linky" if detail else "Detail zařízení", "type": "link",
                       "url": "/d/plc-line-overview" if detail else "/d/plc-machine-detail", "includeVars": True, "keepTime": True}],
            "annotations": {"list": []}}



def rolling_production(extra='prefix=~"05|10|15|20"', total=False):
    """One-hour counter increase at every plotted timestamp, never rate*3600."""
    value = f'increase({selector("br08_prefix_total", extra)}[1h])'
    if total:
        value = f'sum by(job,instance) ({value})'
    coverage = f'increase({selector("line_observed_seconds_total")}[1h]) >= 3420'
    br_valid = selector("line_br_data_valid", 'station="BR08"')
    return fresh(f'({value}) and on(job,instance) ({coverage}) and on(job,instance) (min_over_time({br_valid}[1h]) == 1)')


def production_panel():
    p = panel(60, "Produkce BR08 · klouzavý součet za posledních 60 minut", rolling_production(total=True),
              0, 5, 24, 10, "timeseries", unit="locale", legend="Celkem",
              description="Každý bod = přírůstek čítače za předchozích 60 minut. Celkem = 05 + 10 + 15 + 20. Zdroj: původní BR08 čítače s deduplikací BoxID; nejde o garantované fyzické průjezdy. Vyžaduje alespoň 95 % časového pokrytí a platné BR08 vzorky v hodinovém okně. Barevné oblasti jsou pozorovaná čekání a hlášené stavy; souběh s poklesem neprokazuje příčinu.")
    p["fieldConfig"]["defaults"]["min"] = 0
    p["fieldConfig"]["defaults"]["custom"].update(axisLabel="boxů / posledních 60 min", fillOpacity=0, lineWidth=2)
    p["options"]["legend"].update(displayMode="table", placement="right", width=190, calcs=["lastNotNull"])
    p["fieldConfig"]["overrides"].append(override("Celkem", **{"color":{"mode":"fixed","fixedColor":"text"}, "custom.lineWidth":3}))
    for i,(prefix,color) in enumerate((("05","blue"),("10","green"),("15","orange"),("20","purple")),1):
        label = "Boxy " + prefix
        p["targets"].append(dict(p["targets"][0], refId=chr(65+i), expr=rolling_production(f'prefix="{prefix}"'), legendFormat=label))
        p["fieldConfig"]["overrides"].append(override(label, color={"mode":"fixed","fixedColor":color}))
    return p


def production_annotations():
    station = 'station=~"${incident_station:regex}"'
    def annotation(name, expr, color, title, text, tags="station"):
        return {"name":name,"enable":True,"hide":False,"type":"dashboard","datasource":DS,
                "expr":expr,"step":"10s","useValueForTime":False,"iconColor":color,
                "titleFormat":title,"textFormat":text,"tagKeys":tags,
                "filter":{"exclude":False,"ids":[60,21]}}
    events = [annotation("Čekání", fresh(selector("line_waiting_active", station)), "#FFB357",
               "{{station}} · čekání před zařízením", "Prostojový bit DB: obsazený snímač, stojící motor a zapnutý dopravník. Neurčuje příčinu.")]
    for code,name,color,text in (
        (5,"Materiál stop","#F2495C","Zařízení hlásí nedostatek materiálu."),
        (6,"Chyba stroje","#E02F44","Aktivní chybový stav stroje."),
        (7,"Bezpečnost","#B877D9","Bezpečnost zařízení není připravena."),
    ):
        events.append(annotation(name, fresh(f'{selector("line_machine_state", station)} == {code}'), color,
                                 "{{station}} · " + name, text + " Stav dle zobrazovací priority; souběžné signály jsou v detailu."))
    br_valid = selector("line_br_data_valid", 'station="BR08"')
    invalid = f'((1 - {selector("plc_data_valid")}) and on(job,instance) ({selector("up")} == 1)) or (1 - {selector("up")}) or ({fresh(f"1 - {br_valid}")})'
    events.append(annotation("Výpadek dat", invalid, "#8E8E8E", "Neplatná nebo nedostupná data",
                             "V tomto intervalu nelze stav linky spolehlivě posoudit.", ""))
    return events

def build():
    br08_observations = increase("line_br_observations_total", 'station="BR08"')
    good_count = fresh(f'{selector("dnes_pocet_boxu")} and on(job,instance) ({selector("line_daily_box_count_valid")} == 1)')
    tempo = fresh(f'rate({selector("line_observed_box_increments_total")}[5m]) * 3600 and on(job,instance) (rate({selector("line_observed_seconds_total")}[5m]) >= 0.9)')
    plan = fresh(f'100 * {selector("dnes_pocet_boxu")} / on(job,instance) ({selector("target_pocet_boxu")} > 0) and on(job,instance) ({selector("excel_active_target_is_today")} == 1) and on(job,instance) ({selector("excel_data_valid")} == 1) and on(job,instance) ({selector("line_daily_box_count_valid")} == 1)')
    coverage = f'clamp_max(100 * {increase("line_observed_seconds_total")} / ${{__range_s}}, 100)'
    wait = increase("line_waiting_seconds_total")
    status_map = {-1: ("Bez dat", "gray"), 0: ("Neaktivní", "blue"), 1: ("Aktivní", "orange")}
    panels = [row(1, "Hlavní KPI", 0),
        panel(2, "Boxy dnes", good_count, 0, 1, 4, 3, unit="locale", description="Signed Int z PLC, senzor před vraty 38. Nejde o potvrzenou expedici."),
        panel(3, "Tempo · boxů/h", tempo, 4, 1, 4, 3, unit="locale", description="Přírůstky za 5 minut, pouze při nejméně 90 % pokrytí měřením."),
        panel(4, "Dnešní plán · %", plan, 8, 1, 4, 3, unit="percent"),
        panel(5, "BR08 · pozorování", f'sum({br08_observations})', 12, 1, 4, 3, unit="locale", description="Počet změn neprázdného BR snapshotu. Není počtem unikátních fyzických průjezdů."),
        panel(6, "Pokrytí dat", coverage, 16, 1, 4, 3, unit="percent", description="Podíl pozorovaného času v časovém výběru. Nejde o dostupnost linky ani OEE.", color="green"),
        panel(7, "PLC data", f'{selector("up")} * on(job,instance) {selector("plc_data_valid")}', 20, 1, 4, 3, mappings={0: ("Neplatná", "red"), 1: ("Aktuální", "green")}),
        unavailable(8, "OEE", "Chybí definice plánovaného času, ideálního taktu, kvality a rozhodujícího stavu celé linky.", 0, 4, 4),
        unavailable(9, "Predikce směny", "Chybí potvrzené směny, přestávky a definice dokončeného boxu. Zobrazení nuly by bylo zavádějící.", 4, 4, 4),
        panel(10, "Čekání · součet stanic", f'sum({wait})', 8, 4, 4, 3, unit="s", color="orange", description="Součet časů stanic včetně krátkých čekání. Souběžná čekání se sčítají; není to prostoj celé linky."),
        station_names(panel(11, "Čekání podle stanice · výběr", wait, 12, 4, 12, 3, "bargauge", unit="s", legend="{{station}}", color="orange")),
        row(20, "Výkon a čekání v čase", 7),
        panel(21, "Pozorované tempo · boxů/h", tempo, 0, 8, 12, 6, "timeseries", unit="locale", legend="Senzor před vraty 38"),
        panel(22, "Plnění dnešního plánu · %", plan, 12, 8, 6, 6, "timeseries", unit="percent", legend="Dnešní plán"),
        station_names(panel(23, "Čekání před zařízeními", online(selector("line_waiting_active")), 18, 8, 6, 6, "state-timeline", legend="{{station}}", mappings=status_map)),
        row(30, "Aktuální signály strojů", 14),
        signal_board(31, "Gebhardt / Smartlog", [("M1", "Pohon M1", False), ("M2", "Pohon M2", False), ("smartlog_zapnut", "Dopravník", False), ("vahaChod", "Chod váhy", False)], 0, 15),
        signal_board(32, "Ranpak V10", [("V10_"+key, label, bad) for key,label,bad in RANPAK_SIGNALS], 3, 15),
        signal_board(33, "Ranpak V20", [("V20_"+key, label, bad) for key,label,bad in RANPAK_SIGNALS], 6, 15),
        signal_board(34, "AKL pravá · P1", [("Line1_"+key, label, bad) for key,label,bad in AKL_SIGNALS], 9, 15),
        signal_board(35, "AKL levá · P2", [("Line2_"+key, label, bad) for key,label,bad in AKL_SIGNALS], 12, 15),
        signal_board(36, "Teleskopy", [("pasChod_levy_T1", "T1 · chod", False), ("safetyReady_levy_T1", "T1 · bezpečnost", False), ("pasChod_pravy_T2", "T2 · chod", False), ("safetyReady_pravy_T2", "T2 · bezpečnost", False)], 15, 15),
        estop_board(37, "Smartlog · ESTOP", "smartlog_estop_active", "{{estop}}", 18, 15),
        signal_board(38, "Gebhardt · ESTOP", [(f"aktivovanoTlacitko{i}", f"Tlačítko {i}", True) for i in range(1,7)], 21, 15),
        row(40, "Stavy a materiálové události", 23),
        station_names(panel(41, "Stavy zařízení", online(selector("line_machine_state")), 0, 24, 12, 7, "state-timeline", legend="{{station}}", mappings=STATES)),
        panel(42, "Ranpak · aktivní chyba stroje", fresh(selector("V10_bMachineError")), 12, 24, 6, 7, "state-timeline", legend="V10", mappings={0: ("Bez chyby", "green"), 1: ("Chyba", "red")}),
        panel(43, "Materiál · zachycené aktivace stop", increase("line_material_activations_total", 'level="stop"'), 18, 24, 6, 7, "bargauge", legend="{{machine}} · {{material}}", color="orange"),
        panel(44, "AKL · materiálové stavy", online(selector("line_material_active", 'machine=~"AKL1|AKL2"')), 0, 31, 12, 7, "state-timeline", legend="{{machine}} · {{material}} · {{level}}", mappings=status_map),
        panel(45, "Varování → stop · poslední měření", fresh(selector("line_material_warning_lead_seconds")), 12, 31, 6, 7, "bargauge", unit="s", legend="{{machine}} · {{material}}", description="Vyžaduje předchozí zachycené varování bez mezery v datech. Lepidlo předběžné varování nemá."),
        panel(46, "AKL · průchod bez etiketování", online(selector("line_label_bypass_active")), 18, 31, 6, 7, "state-timeline", legend="{{machine}}", mappings={-1:("Bez dat","gray"),0:("Vypnuto","blue"),1:("Bez etiketování","purple")}),
        row(50, "BR / Plausicheck a kvalita sběru", 38),
        clean_table(panel(51, "BR · aktuální odpovědi", fresh(selector("line_br_response_code")), 0, 39, 6, 7, "table"), ["station","Value"], {"station":"Pozice","Value":"Kód odpovědi"}),
        panel(52, "BR · chybová pozorování ve výběru", increase("line_br_observations_total", 'result="error"'), 6, 39, 6, 7, "bargauge", legend="{{station}}", color="red"),
        clean_table(panel(53, "BR · kvalita čtení", online(selector("line_br_data_valid")), 12, 39, 6, 7, "table", mappings={0:("Neplatné","red"),1:("Platné","green")}), ["station","Value"], {"station":"Pozice","Value":"Stav"}),
        panel(54, "Plausicheck · ShippingLabel", online(selector("line_plausi_label_present")), 18, 39, 6, 3, mappings={-1:("Bez dat","gray"),0:("Prázdný","gray"),1:("Vyplněný","blue")}, description="Obsah řetězce neprokazuje správnost etikety. Detail je v historii boxu."),
        panel(55, "Archiv", online(selector("event_journal_healthy")), 18, 42, 6, 4, mappings={0:("Nedostupný","red"),1:("Zapisuje","green")}),
        panel(56, "Zahozené záznamy · od startu", selector("event_journal_dropped_total"), 0, 46, 8, 3, unit="locale"),
        panel(57, "Nespojitosti počítadla · od startu", selector("line_box_counter_discontinuities_total"), 8, 46, 8, 3, unit="locale"),
        panel(58, "Stáří PLC dat", selector("plc_data_staleness_seconds"), 16, 46, 8, 3, unit="s"),
    ]
    layout = {
        31:(0,15,4,8), 32:(4,15,4,8), 33:(8,15,4,8),
        34:(12,15,4,8), 35:(16,15,4,8), 36:(20,15,4,8),
        37:(0,23,6,8), 38:(6,23,4,8), 41:(10,23,14,8),
        40:(0,31,24,1), 42:(0,32,6,7), 43:(6,32,6,7), 44:(12,32,12,7),
        45:(0,39,12,6), 46:(12,39,12,6), 50:(0,45,24,1),
        51:(0,46,6,7), 52:(6,46,6,7), 53:(12,46,6,7),
        54:(18,46,6,3), 55:(18,49,6,4), 56:(0,53,8,3), 57:(8,53,8,3), 58:(16,53,8,3),
    }
    for p in panels:
        if p["id"] in layout:
            p["gridPos"] = dict(zip(("x","y","w","h"),layout[p["id"]]))
        if p["id"] in range(31,37):
            p["description"] = ""
        if p["id"] in (37,38):
            p["options"].update(namePlacement="left")
        if p["id"] in (43,45):
            for machine in ("AKL1","AKL2","V10","V20"):
                for key,name in MATERIAL_NAMES.items():
                    p["fieldConfig"]["overrides"].append(override(f"{machine} · {key}",displayName=f"{machine} · {name.lower()}"))
    panels.sort(key=lambda p:(p["gridPos"]["y"],p["gridPos"]["x"]))
    # Add the second machine to the existing error timeline, without deriving counts from status changes.
    error_panel = next(p for p in panels if p["id"] == 42)
    error_panel["targets"].append(dict(error_panel["targets"][0], refId="B", expr=fresh(selector("V20_bMachineError")), legendFormat="V20"))
    # Keep the high-density summary readable with short labels in the bar chart.
    next(p for p in panels if p["id"] == 11)["fieldConfig"]["overrides"] = [override(k, displayName=k if k != "vaha" else "Váha") for k in NAMES]
    next(p for p in panels if p["id"] == 11)["options"].update(orientation="vertical", namePlacement="auto", displayMode="basic")
    for p in panels:
        if p["id"] == 44:
            for machine in ("AKL1", "AKL2"):
                for key, name in MATERIAL_NAMES.items():
                    for level, translated in (("warning","varování"),("stop","stop")):
                        p["fieldConfig"]["overrides"].append(override(f"{machine} · {key} · {level}", displayName=f"{machine} · {name.lower()} · {translated}"))
        if p["id"] in (32,33,34,35):
            station = {32:"V10",33:"V20",34:"AKL1",35:"AKL2"}[p["id"]]
            p["links"] = [{"title":"Detail zařízení", "url":f'/d/plc-machine-detail?var-station={station}&var-job=${{job:percentencode}}&var-instance=${{instance:percentencode}}&var-DS_PROMETHEUS=${{DS_PROMETHEUS:percentencode}}&var-history_url=${{history_url:percentencode}}&${{__url_time_range}}'}]
    station = 'station=~"${station:regex}"'
    machine = 'machine=~"${station:regex}"'
    detail = [row(1, "Detail zařízení · ${station}", 0),
        panel(2, "Aktuální stav", online(selector("line_machine_state", station)), 0, 1, 8, 3, mappings=STATES),
        panel(3, "Aktuální čekání", fresh(selector("line_waiting_current_seconds", station)), 8, 1, 8, 3, unit="s", color="orange"),
        panel(4, "Čekání ve výběru", increase("line_waiting_seconds_total", station), 16, 1, 8, 3, unit="s", color="orange"),
        station_names(panel(5, "Historie stavů", online(selector("line_machine_state", station)), 0, 4, 24, 5, "state-timeline", legend="{{station}}", mappings=STATES)),
        panel(6, "Materiálové stavy", online(selector("line_material_active", machine)), 0, 9, 12, 7, "state-timeline", legend="{{material}} · {{level}}", mappings=status_map),
        clean_table(panel(7, "Souběh čekání a stavu", fresh(selector("line_waiting_coincidence", station)), 12, 9, 12, 7, "table", description="Souběh s prioritním zobrazeným stavem, nikoli prokázaná příčina čekání."), ["condition","Value"], {"condition":"Současný stav","Value":"Aktivní"}),
        panel(8, "Čas podle zobrazovaného stavu", increase("line_machine_state_seconds_total", station) + " > 0", 0, 16, 24, 6, "bargauge", unit="s", legend="{{state}}", description="Výlučné stavy uvnitř jedné stanice podle priority zobrazení. Není OEE. Neznámé intervaly se nepočítají."),
    ]
    detail[6]["fieldConfig"]["overrides"].append(override("condition", mappings=mapping({key:(value,"text") for key,value in CONDITIONS.items()})))
    detail[6]["fieldConfig"]["overrides"].append(override("Value", mappings=mapping({0:("Ne","gray"),1:("Ano","orange")})))
    detail[7]["fieldConfig"]["overrides"] += [override(str(code), displayName=name, color={"mode":"fixed","fixedColor":color}) for code,(name,color) in STATES.items() if code>=0]
    for key,name in MATERIAL_NAMES.items():
        for level,label in (("warning","varování"),("stop","stop")):
            detail[5]["fieldConfig"]["overrides"].append(override(f"{key} · {level}",displayName=f"{name} · {label}"))
    # Place the main production plot immediately after the compact KPI row.
    for p in panels:
        if p["gridPos"]["y"] >= 4:
            p["gridPos"]["y"] += 11
        if p["id"] == 5:
            p["title"] = "BR08 · poslední hodina"
            p["targets"][0]["expr"] = rolling_production(total=True)
            p["description"] = "Stejný hodinový součet 05 + 10 + 15 + 20 jako hlavní graf. Prvních přibližně 60 minut nebo při nedostatečném pokrytí není dostupný."
        if p["id"] == 21:
            p["description"] = "Rychlá odezva: přírůstky senzoru před vraty 38 za 5 minut přepočtené na boxů/h. Jiné místo a jiné okno než hlavní BR08 graf. Události na stejné časové ose umožňují porovnání, nikoli důkaz příčiny."
    panels += [row(61, "Produkce a události linky", 4), production_panel()]
    panels.sort(key=lambda p:(p["gridPos"]["y"],p["gridPos"]["x"]))
    overview = dashboard("plc-line-overview", "Smartlog · přehled linky", panels)
    overview["templating"]["list"].append({"name":"incident_station","label":"Události zařízení","type":"custom",
        "query":",".join(f"{label} : {key}" for key,label in NAMES.items()), "multi":True,"includeAll":True,"allValue":".*",
        "current":{"text":["All"],"value":["$__all"]}})
    overview["annotations"]["list"] = production_annotations()
    return {"line-overview.json": overview,
            "machine-detail.json": dashboard("plc-machine-detail", "Smartlog · detail zařízení", detail, True)}


if __name__ == "__main__":
    for filename, content in build().items():
        (ROOT / "grafana").mkdir(exist_ok=True)
        (ROOT / "grafana" / filename).write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n")
