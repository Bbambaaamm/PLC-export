"""Generate compact operations dashboards using native Grafana panels."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = {"type": "prometheus", "uid": "${DS_PROMETHEUS}"}
S = 'job="${job}",instance="${instance}"'
WINDOW = '${__range_s}s'
STATES = {
    -1: ("Bez platných dat", "gray"), 0: ("Bez potvrzení chodu", "gray"),
    1: ("Připraveno", "green"), 2: ("Chod potvrzen", "green"),
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


def signal_board(pid, title, signals, x, y, w=4, h=7):
    """Compact diagnostic matrix: field name + semantic status dot, no decorative bars."""
    p = panel(pid, title, "", x, y, w, h, "stat")
    p["targets"] = []
    p["options"] = {
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
        "colorMode": "value", "graphMode": "none", "textMode": "value_and_name",
        "justifyMode": "center", "orientation": "horizontal", "wideLayout": True,
        "text": {"titleSize": 11, "valueSize": 19},
    }
    p["fieldConfig"]["defaults"].update(min=0, max=1, noValue="●")
    p["fieldConfig"]["overrides"] = []
    for i, (metric, label, bad) in enumerate(signals):
        p["targets"].append({"refId": chr(65+i), "expr": fresh(selector(metric)), "legendFormat": label,
                             "instant": True, "range": False, "datasource": DS})
        if "varování" in label:
            values = {0: ("●", "gray"), 1: ("●", "orange")}
        elif "etiketování" in label:
            values = {0: ("●", "gray"), 1: ("●", "purple")}
        elif bad:
            values = {0: ("●", "green"), 1: ("●", "red")}
        else:
            values = {0: ("●", "gray"), 1: ("●", "green")}
        p["fieldConfig"]["overrides"].append(override(label, mappings=mapping(values)))
    return p


def estop_board(pid, title, metric, legend, x, y, w=12, h=5):
    """Emergency-stop matrix: a compact named dot per circuit."""
    p = panel(pid, title, fresh(selector(metric)), x, y, w, h, "stat", legend=legend,
              mappings={-1: ("●", "gray"), 0: ("●", "green"), 1: ("●", "red")})
    p["options"] = {
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
        "colorMode": "value", "graphMode": "none", "textMode": "value_and_name",
        "justifyMode": "center", "orientation": "horizontal", "wideLayout": True,
        "text": {"titleSize": 11, "valueSize": 22},
    }
    p["fieldConfig"]["defaults"].update(min=-1, max=1)
    return p


def gebhardt_estop_board(pid, x, y, w=10, h=5):
    p = panel(pid, "Gebhardt · nouzová tlačítka", "", x, y, w, h, "stat",
              mappings={-1: ("●", "gray"), 0: ("●", "green"), 1: ("●", "red")})
    p["targets"] = []
    for i in range(1, 7):
        p["targets"].append({"refId": chr(64+i), "expr": fresh(selector(f"aktivovanoTlacitko{i}")),
                             "legendFormat": f"Tlačítko {i}", "instant": True, "range": False, "datasource": DS})
    p["options"] = {
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
        "colorMode": "value", "graphMode": "none", "textMode": "value_and_name",
        "justifyMode": "center", "orientation": "horizontal", "wideLayout": True,
        "text": {"titleSize": 11, "valueSize": 22},
    }
    p["fieldConfig"]["defaults"].update(min=-1, max=1)
    return p


def thresholds(p, steps):
    p["fieldConfig"]["defaults"]["color"] = {"mode": "thresholds"}
    p["fieldConfig"]["defaults"]["thresholds"] = {
        "mode": "absolute",
        "steps": [{"color": color, "value": value} for color, value in steps],
    }
    return p


def machine_card(pid, station, x, y, w, h=4):
    p = panel(pid, NAMES[station], online(selector("line_machine_state", f'station="{station}"')),
              x, y, w, h, mappings=STATES)
    p["options"].update(textMode="value", colorMode="value")
    p["options"]["text"] = {"titleSize": 11, "valueSize": 20}
    p["links"] = [{
        "title": "Detail zařízení",
        "url": f'/d/plc-machine-detail?var-station={station}&var-job=${{job:percentencode}}&var-instance=${{instance:percentencode}}&var-DS_PROMETHEUS=${{DS_PROMETHEUS:percentencode}}&var-history_url=${{history_url:percentencode}}&${{__url_time_range}}'
    }]
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
        {"name": "DS_PROMETHEUS", "label": "Zdroj", "type": "datasource", "query": "prometheus", "regex": "/^Zoo$/", "refresh": 1},
        {"name": "job", "label": "Exportér", "type": "query", "datasource": DS, "query": "label_values(plc_data_valid, job)", "refresh": 1, "multi": False, "includeAll": False},
        {"name": "instance", "label": "Instance", "type": "query", "datasource": DS, "query": 'label_values(plc_data_valid{job="${job}"}, instance)', "refresh": 1, "multi": False, "includeAll": False},
        {"name": "history_url", "label": "Adresa historie", "type": "textbox", "hide": 2, "query": "http://EXPORTER:8000/history", "current": {"text": "http://EXPORTER:8000/history", "value": "http://EXPORTER:8000/history"}},
    ]
    if detail:
        variables.append({"name": "station", "label": "Zařízení", "type": "custom", "query": ",".join(NAMES), "current": {"text": "V10", "value": "V10"}, "multi": False, "includeAll": False})
    return {"uid": uid, "title": title, "schemaVersion": 39, "version": 4, "timezone": "Europe/Prague",
            "description": "Profesionální provozní přehled Smartlog linky. Overview zobrazuje pouze rozhodovací informace; detailní PLC signály jsou oddělené v diagnostice. Čekání není automaticky porucha a BR pozorování nejsou garantované fyzické průjezdy.",
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
    p = panel(60, "Produkce · BR08 za posledních 60 minut", rolling_production(total=True),
              0, 6, 24, 10, "timeseries", unit="locale", legend="Celkem",
              description="Každý bod je přírůstek čítače za předchozích 60 minut. Celkem = 05 + 10 + 15 + 20. Stavové souvislosti jsou v časově zarovnaném panelu pod grafem, aby produkční křivky zůstaly čitelné.")
    p["fieldConfig"]["defaults"]["min"] = 0
    p["fieldConfig"]["defaults"]["custom"].update(axisLabel="boxů / posledních 60 min", fillOpacity=0, lineWidth=2)
    p["options"]["legend"].update(displayMode="table", placement="right", width=180, calcs=["lastNotNull"])
    p["fieldConfig"]["overrides"].append(override("Celkem", **{"color":{"mode":"fixed","fixedColor":"text"}, "custom.lineWidth":4}))
    for i,(prefix,color) in enumerate((("05","blue"),("10","green"),("15","orange"),("20","purple")),1):
        label = "Boxy " + prefix
        p["targets"].append(dict(p["targets"][0], refId=chr(65+i), expr=rolling_production(f'prefix="{prefix}"'), legendFormat=label))
        p["fieldConfig"]["overrides"].append(override(label, **{"color":{"mode":"fixed","fixedColor":color}, "custom.lineWidth":2}))
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
    good_count = fresh(f'{selector("dnes_pocet_boxu")} and on(job,instance) ({selector("line_daily_box_count_valid")} == 1)')
    tempo = fresh(f'rate({selector("line_observed_box_increments_total")}[5m]) * 3600 and on(job,instance) (rate({selector("line_observed_seconds_total")}[5m]) >= 0.9)')
    plan = fresh(f'100 * {selector("dnes_pocet_boxu")} / on(job,instance) ({selector("target_pocet_boxu")} > 0) and on(job,instance) ({selector("excel_active_target_is_today")} == 1) and on(job,instance) ({selector("excel_data_valid")} == 1) and on(job,instance) ({selector("line_daily_box_count_valid")} == 1)')
    coverage = f'clamp_max(100 * {increase("line_observed_seconds_total")} / ${{__range_s}}, 100)'
    wait = increase("line_waiting_seconds_total")
    active_waiting = fresh(f'sum by(job,instance) ({selector("line_waiting_active")} == bool 1)')
    critical = fresh(
        f'sum by(job,instance) (({selector("line_machine_state")} == bool 5) + '
        f'({selector("line_machine_state")} == bool 6) + '
        f'({selector("line_machine_state")} == bool 7))'
    )
    status_map = {-1: ("Bez dat", "gray"), 0: ("Neaktivní", "gray"), 1: ("Aktivní", "orange")}

    # ------------------------------------------------------------------
    # Professional overview: decision-first, technical detail moved out.
    # ------------------------------------------------------------------
    overview_panels = [row(1, "Přehled linky", 0),
        panel(2, "Boxy dnes", good_count, 0, 1, 4, 4, unit="locale",
              description="Aktuální denní PLC čítač. Nejde o potvrzenou expedici."),
        panel(3, "Tempo · boxů/h", tempo, 4, 1, 4, 4, unit="locale",
              description="Přírůstky za 5 minut, pouze při nejméně 90 % pokrytí měřením."),
        panel(5, "BR08 · poslední hodina", rolling_production(total=True), 8, 1, 4, 4, unit="locale",
              description="Součet prefixů 05/10/15/20 za klouzavých 60 minut."),
        thresholds(panel(12, "Aktivní čekání", active_waiting, 12, 1, 4, 4, unit="locale",
                         description="Počet zařízení, která právě hlásí čekání."), [("green", None), ("orange", 1)]),
        thresholds(panel(13, "Kritické stavy", critical, 16, 1, 4, 4, unit="locale",
                         description="Materiál stop + chyba stroje + nepřipravená bezpečnost."), [("green", None), ("red", 1)]),
        panel(7, "PLC data", f'{selector("up")} * on(job,instance) {selector("plc_data_valid")}', 20, 1, 4, 4,
              mappings={0: ("Neplatná", "red"), 1: ("Aktuální", "green")}),
        production_panel(),
        row(20, "Stav zařízení v čase", 16),
        station_names(panel(41, "Provozní stav zařízení", online(selector("line_machine_state")),
                            0, 17, 24, 6, "state-timeline", legend="{{station}}", mappings=STATES,
                            description="Jedna prioritní provozní barva na zařízení. Detailní souběžné bity jsou v diagnostice.")),
        row(30, "Aktuální stav zařízení", 23),
        machine_card(31, "V10", 0, 24, 6), machine_card(32, "V20", 6, 24, 6),
        machine_card(33, "AKL1", 12, 24, 6), machine_card(34, "AKL2", 18, 24, 6),
        machine_card(35, "T1", 0, 28, 8), machine_card(36, "T2", 8, 28, 8),
        machine_card(37, "vaha", 16, 28, 8),
        row(40, "Bezpečnost", 32),
        estop_board(42, "Smartlog · nouzová tlačítka", "smartlog_estop_active", "{{estop}}", 0, 33, 14, 5),
        gebhardt_estop_board(43, 14, 33, 10, 5),
        row(50, "Výkon a čekání", 38),
        panel(51, "Pozorované tempo · boxů/h", tempo, 0, 39, 12, 6, "timeseries", unit="locale",
              legend="Senzor před vraty 38",
              description="Rychlá odezva za 5 minut; jiný měřicí bod než BR08."),
        station_names(panel(52, "Čekání podle stanice", wait, 12, 39, 12, 6, "bargauge",
                            unit="s", legend="{{station}}", color="orange",
                            description="Součet časů stanic ve zvoleném období. Souběžná čekání se sčítají.")),
        row(60, "Kvalita sběru a plán", 45),
        thresholds(panel(61, "Pokrytí dat", coverage, 0, 46, 6, 3, unit="percent",
                         description="Podíl pozorovaného času ve výběru; není to OEE."), [("red", None), ("orange", 80), ("green", 95)]),
        panel(62, "Archiv", online(selector("event_journal_healthy")), 6, 46, 6, 3,
              mappings={0: ("Nedostupný", "red"), 1: ("Zapisuje", "green")}),
        panel(63, "Stáří PLC dat", selector("plc_data_staleness_seconds"), 12, 46, 6, 3, unit="s"),
        panel(64, "Dnešní plán · %", plan, 18, 46, 6, 3, unit="percent",
              description="Zobrazuje se pouze při platném dnešním plánu z Excelu."),
    ]
    # Overview bars should be information-dense but visually quiet.
    overview_panels[-6]["options"].update(orientation="horizontal", namePlacement="left")
    overview = dashboard("plc-line-overview", "Smartlog · provozní přehled", overview_panels)
    overview["annotations"]["list"] = []
    overview["links"] = [
        {"title":"Technická diagnostika","type":"link","url":"/d/plc-technical-diagnostics","includeVars":True,"keepTime":True},
        {"title":"Detail zařízení","type":"link","url":"/d/plc-machine-detail","includeVars":True,"keepTime":True},
        {"title":"Historie boxů / incidentů","type":"link","url":"${history_url}","targetBlank":True},
    ]

    # ------------------------------------------------------------------
    # Technical diagnostics: dense PLC/status data belongs here.
    # ------------------------------------------------------------------
    technical = [row(100, "Detailní signály zařízení", 0),
        signal_board(101, "Gebhardt / Smartlog",
                     [("M1","Pohon M1",False),("M2","Pohon M2",False),("smartlog_zapnut","Dopravník",False),("vahaChod","Chod váhy",False)],
                     0,1,4,7),
        signal_board(102, "Ranpak V10", [("V10_"+key,label,bad) for key,label,bad in RANPAK_SIGNALS], 4,1,4,7),
        signal_board(103, "Ranpak V20", [("V20_"+key,label,bad) for key,label,bad in RANPAK_SIGNALS], 8,1,4,7),
        signal_board(104, "AKL pravá · P1", [("Line1_"+key,label,bad) for key,label,bad in AKL_SIGNALS], 12,1,4,7),
        signal_board(105, "AKL levá · P2", [("Line2_"+key,label,bad) for key,label,bad in AKL_SIGNALS], 16,1,4,7),
        signal_board(106, "Teleskopy",
                     [("pasChod_levy_T1","T1 · chod",False),("safetyReady_levy_T1","T1 · bezpečnost",False),
                      ("pasChod_pravy_T2","T2 · chod",False),("safetyReady_pravy_T2","T2 · bezpečnost",False)],
                     20,1,4,7),
        row(110, "Bezpečnost", 8),
        estop_board(111, "Smartlog · nouzová tlačítka", "smartlog_estop_active", "{{estop}}", 0,9,14,5),
        gebhardt_estop_board(112,14,9,10,5),
        row(120, "Stavy a materiálové události", 14),
        station_names(panel(121, "Historie provozních stavů", online(selector("line_machine_state")),
                            0,15,24,7,"state-timeline",legend="{{station}}",mappings=STATES)),
        panel(122, "Ranpak · chyba stroje", fresh(selector("V10_bMachineError")), 0,22,8,6,
              "state-timeline",legend="V10",mappings={0:("Bez chyby","green"),1:("Chyba","red")}),
        panel(123, "Materiál · aktivace stop", increase("line_material_activations_total",'level="stop"'),
              8,22,8,6,"bargauge",legend="{{machine}} · {{material}}",color="orange"),
        panel(124, "AKL · materiálové stavy", online(selector("line_material_active",'machine=~"AKL1|AKL2"')),
              16,22,8,6,"state-timeline",legend="{{machine}} · {{material}} · {{level}}",mappings=status_map),
        panel(125, "Varování → stop · poslední měření", fresh(selector("line_material_warning_lead_seconds")),
              0,28,12,6,"bargauge",unit="s",legend="{{machine}} · {{material}}"),
        panel(126, "AKL · průchod bez etiketování", online(selector("line_label_bypass_active")),
              12,28,12,6,"state-timeline",legend="{{machine}}",
              mappings={-1:("Bez dat","gray"),0:("Vypnuto","gray"),1:("Bez etiketování","purple")}),
        row(130, "BR / Plausicheck", 34),
        clean_table(panel(131, "BR · aktuální odpovědi", fresh(selector("line_br_response_code")),
                          0,35,6,7,"table"), ["station","Value"], {"station":"Pozice","Value":"Kód odpovědi"}),
        panel(132, "BR · chybová pozorování", increase("line_br_observations_total",'result="error"'),
              6,35,6,7,"bargauge",legend="{{station}}",color="red"),
        clean_table(panel(133, "BR · kvalita čtení", online(selector("line_br_data_valid")),
                          12,35,6,7,"table",mappings={0:("Neplatné","red"),1:("Platné","green")}),
                    ["station","Value"], {"station":"Pozice","Value":"Stav"}),
        panel(134, "Plausicheck · ShippingLabel", online(selector("line_plausi_label_present")),
              18,35,6,3,mappings={-1:("Bez dat","gray"),0:("Prázdný","gray"),1:("Vyplněný","green")}),
        panel(135, "Archiv", online(selector("event_journal_healthy")), 18,38,6,4,
              mappings={0:("Nedostupný","red"),1:("Zapisuje","green")}),
        row(140, "Sběr a integrita", 42),
        panel(141, "Zahozené záznamy · od startu", selector("event_journal_dropped_total"), 0,43,8,3,unit="locale"),
        panel(142, "Nespojitosti počítadla · od startu", selector("line_box_counter_discontinuities_total"), 8,43,8,3,unit="locale"),
        panel(143, "Stáří PLC dat", selector("plc_data_staleness_seconds"), 16,43,8,3,unit="s"),
    ]
    # V20 is the second series in the same machine-error timeline.
    technical[11]["targets"].append(dict(technical[11]["targets"][0], refId="B",
                                         expr=fresh(selector("V20_bMachineError")), legendFormat="V20"))
    technical_doc = dashboard("plc-technical-diagnostics", "Smartlog · technická diagnostika", technical)
    technical_doc["links"] = [
        {"title":"Provozní přehled","type":"link","url":"/d/plc-line-overview","includeVars":True,"keepTime":True},
        {"title":"Detail zařízení","type":"link","url":"/d/plc-machine-detail","includeVars":True,"keepTime":True},
        {"title":"Historie boxů / incidentů","type":"link","url":"${history_url}","targetBlank":True},
    ]

    # ------------------------------------------------------------------
    # Per-machine drill-down.
    # ------------------------------------------------------------------
    station = 'station="${station}"'
    machine = 'machine="${station}"'
    detail = [row(1, "Detail zařízení · ${station}", 0),
        panel(2, "Aktuální stav", online(selector("line_machine_state", station)), 0,1,8,3,mappings=STATES),
        panel(3, "Aktuální čekání", fresh(selector("line_waiting_current_seconds", station)), 8,1,8,3,unit="s",color="orange"),
        panel(4, "Čekání ve výběru", increase("line_waiting_seconds_total", station), 16,1,8,3,unit="s",color="orange"),
        station_names(panel(5, "Historie stavů", online(selector("line_machine_state", station)),
                            0,4,24,6,"state-timeline",legend="{{station}}",mappings=STATES)),
        panel(6, "Materiálové stavy", online(selector("line_material_active", machine)),
              0,10,12,7,"state-timeline",legend="{{material}} · {{level}}",mappings=status_map),
        clean_table(panel(7, "Souběh čekání a stavu", fresh(selector("line_waiting_coincidence", station)),
                          12,10,12,7,"table",description="Souběh s prioritním stavem, nikoli prokázaná příčina."),
                    ["condition","Value"], {"condition":"Současný stav","Value":"Aktivní"}),
        panel(8, "Čas podle zobrazovaného stavu", increase("line_machine_state_seconds_total", station) + " > 0",
              0,17,24,6,"bargauge",unit="s",legend="{{state}}",
              description="Výlučné prioritní stavy stanice. Není OEE."),
    ]
    detail[6]["fieldConfig"]["overrides"].append(override("condition", mappings=mapping({key:(value,"text") for key,value in CONDITIONS.items()})))
    detail[6]["fieldConfig"]["overrides"].append(override("Value", mappings=mapping({0:("Ne","gray"),1:("Ano","orange")})))
    detail[7]["fieldConfig"]["overrides"] += [override(str(code), displayName=name, color={"mode":"fixed","fixedColor":color}) for code,(name,color) in STATES.items() if code>=0]
    detail_doc = dashboard("plc-machine-detail", "Smartlog · detail zařízení", detail, True)
    detail_doc["links"] = [
        {"title":"Provozní přehled","type":"link","url":"/d/plc-line-overview","includeVars":True,"keepTime":True},
        {"title":"Technická diagnostika","type":"link","url":"/d/plc-technical-diagnostics","includeVars":True,"keepTime":True},
        {"title":"Historie boxů / incidentů","type":"link","url":"${history_url}","targetBlank":True},
    ]

    return {
        "line-overview.json": overview,
        "technical-diagnostics.json": technical_doc,
        "machine-detail.json": detail_doc,
    }


if __name__ == "__main__":
    for filename, content in build().items():
        (ROOT / "grafana").mkdir(exist_ok=True)
        (ROOT / "grafana" / filename).write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n")
