"""Bounded-cardinality diagnostics grounded in DB2000; caller holds PLC lock."""
from collections import Counter
import time

from config import PLC_MAX_SAMPLE_GAP_SEC
from db2000 import BR_POSITIONS, ESTOPS, MATERIALS, WAITING, decode_position, response_group
from eventJournal import journal


def machine_state(station, state):
    """Display precedence, not a causal/OEE model. Ready does not mean working."""
    waiting = bool(state.get(WAITING[station]))
    if station in ("V10", "V20"):
        if not state.get(station + "_safetyReady"):
            return 7
        if any(state.get(stop) for (machine, _), (_, stop) in MATERIALS.items() if machine == station):
            return 5
        if state.get(station + "_bMachineError"):
            return 6
        if state.get(station + "_bLidSupplyLow"):
            return 4
        return 3 if waiting else 1 if state.get(station + "_bReadyToReceiveBox") else 0
    if station in ("AKL1", "AKL2"):
        prefix = "Line1" if station == "AKL1" else "Line2"
        if state.get(prefix + "_LabelOut") or state.get(prefix + "_RibbonOut"):
            return 5
        if state.get(prefix + "_PassthroughMode"):
            return 8
        if state.get(prefix + "_LabelWarning") or state.get(prefix + "_RibbonWarning"):
            return 4
        return 3 if waiting else 1 if state.get(prefix + "_SystemReady") else 0
    if station in ("T1", "T2"):
        suffix = "levy_T1" if station == "T1" else "pravy_T2"
        if not state.get("safetyReady_" + suffix):
            return 7
        return 3 if waiting else 2 if state.get("pasChod_" + suffix) else 1
    return 3 if waiting else 2 if state.get("vahaChod") else 0


class LineMonitor:
    def __init__(self, publish=None):
        self.publish = publish or journal.publish
        self.previous_time = None
        self.previous = {}
        self.positions = {}
        self.position_valid = {}
        self.response_counts = Counter()
        self.decode_errors = Counter()
        self.wait_starts = {}
        self.wait_seconds = Counter()
        self.material_seconds = Counter()
        self.material_events = Counter()
        self.warning_starts = {}
        self.warning_leads = {}
        self.box_delta_total = 0
        self.box_discontinuities = 0
        self.covered_seconds = 0.0
        self.sample_count = 0
        self.last_wall = None
        self.machine_states = {}
        self.state_seconds = Counter()

    def emit(self, wall, kind, station, details, box_id=""):
        self.publish(dict(observed_at=wall, kind=kind, station=station, box_id=box_id, details=details))

    def invalidate(self, wall=None):
        if self.previous_time is not None:
            self.emit(time.time() if wall is None else wall, "coverage_gap", "PLC", {"reason": "unknown_interval"})
        self.previous_time = None
        self.previous = {}
        self.wait_starts.clear()
        self.warning_starts.clear()
        self.warning_leads.clear()
        self.machine_states.clear()
        # Keep last BR snapshots to avoid inventing new events on reconnect.

    def observe(self, data, state, wall, mono):
        delta = None if self.previous_time is None else mono - self.previous_time
        if delta is not None and not 0 <= delta <= PLC_MAX_SAMPLE_GAP_SEC:
            self.invalidate(wall)
            delta = None
        if delta is not None:
            self.covered_seconds += delta
        self.sample_count += 1
        for station in WAITING:
            status = machine_state(station, state)
            previous_status = self.machine_states.get(station)
            if delta is not None and previous_status is not None:
                self.state_seconds[(station, previous_status)] += delta
            if status != previous_status:
                self.emit(wall, "machine_snapshot" if previous_status is None else "machine_change", station,
                          {"state": status, "previous_state": previous_status})
            self.machine_states[station] = status
        for station, key in WAITING.items():
            active = bool(state.get(key))
            if delta is not None and self.previous.get(key):
                self.wait_seconds[station] += delta
            if active:
                self.wait_starts.setdefault(station, mono)
            else:
                self.wait_starts.pop(station, None)
        for (machine, material), (warn, stop) in MATERIALS.items():
            pair = (machine, material)
            warning = bool(state.get(warn)) if warn else False
            stopped = bool(state.get(stop))
            if warning and not self.previous.get(warn):
                self.warning_starts[pair] = mono
            for level, key in (("warning", warn), ("stop", stop)):
                if key is None:
                    continue
                active = bool(state.get(key))
                if delta is not None and self.previous.get(key):
                    self.material_seconds[(machine, material, level)] += delta
                if active and key in self.previous and not self.previous[key]:
                    self.material_events[(machine, material, level)] += 1
            if stopped and stop in self.previous and not self.previous[stop]:
                # Require warning in an earlier valid sample, not simultaneous flags.
                start = self.warning_starts.get(pair)
                if warn and self.previous.get(warn) and start is not None:
                    lead = max(0, mono - start)
                    self.warning_leads[pair] = lead
                    self.emit(wall, "material_warning_to_stop", machine, {"material": material, "seconds": lead})
            if not warning:
                self.warning_starts.pop(pair, None)
        for name in BR_POSITIONS:
            try:
                record = decode_position(data, name)
            except (ValueError, UnicodeError):
                if self.position_valid.get(name) != 0:
                    self.emit(wall, "decode_error", name, {"reason": "invalid_DB2000_STRING_or_buffer"})
                self.decode_errors[name] += 1
                self.position_valid[name] = 0
                continue
            self.position_valid[name] = 1
            previous = self.positions.get(name)
            self.positions[name] = record
            # A snapshot change is not a guaranteed completed physical passage.
            if record["box_id"] and record != previous:
                group = response_group(record["code"])
                self.response_counts[(name, group)] += 1
                self.emit(wall, "br_observation", name, record, record["box_id"])
        count = int(state.get("dnes_pocet_boxu", 0))
        old_count = self.previous.get("dnes_pocet_boxu")
        if delta is not None and old_count is not None:
            if count >= old_count >= 0:
                self.box_delta_total += count - old_count
            elif count != old_count:
                self.box_discontinuities += 1
                self.emit(wall, "counter_discontinuity", "Smartlog", {"before": old_count, "after": count})
        signals = dict(state)
        signals.update({"estop_" + name: value for name, value in state.get("smartlog_estops", {}).items()})
        signal_keys = list(WAITING.values()) + [k for pair in MATERIALS.values() for k in pair if k]
        signal_keys += ["V10_bMachineError", "V20_bMachineError", "Line1_PassthroughMode", "Line2_PassthroughMode"]
        signal_keys += ["estop_" + name for name, *_ in ESTOPS]
        for key in signal_keys:
            if key not in self.previous or self.previous[key] != signals.get(key, 0):
                self.emit(wall, "signal_snapshot" if key not in self.previous else "signal_change", key,
                          {"value": int(signals.get(key, 0))})
        self.previous = signals
        self.previous_time = mono
        self.last_wall = wall

    def render(self, state, valid, mono):
        lines = []
        def metric(name, value, labels=None, kind="gauge"):
            if name not in declared:
                lines.extend([f"# HELP {name} DB2000 observed diagnostics", f"# TYPE {name} {kind}"])
                declared.add(name)
            label = ""
            if labels:
                def escape(v):
                    return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                label = "{" + ",".join(f'{k}="{escape(v)}"' for k, v in labels.items()) + "}"
            lines.append(f"{name}{label} {value}")
        declared = set()
        current = lambda value: int(value) if valid else -1
        for name, byte, bit, location in ESTOPS:
            metric("smartlog_estop_active", current(state.get("smartlog_estops", {}).get(name, 0)),
                   {"estop": name, "location": location, "address": f"{byte}.{bit}"})
        for station, key in WAITING.items():
            status = machine_state(station, state)
            metric("line_machine_state", status if valid else -1, {"station": station})
            for code in range(9):
                metric("line_machine_state_seconds_total", self.state_seconds[(station, code)],
                       {"station": station, "state": str(code)}, "counter")
            for cause, code in (("material_stop", 5), ("machine_error", 6), ("safety_not_ready", 7), ("label_bypass", 8)):
                metric("line_waiting_coincidence", current(bool(state.get(key)) and status == code),
                       {"station": station, "condition": cause})
            metric("line_waiting_active", current(state.get(key, 0)), {"station": station})
            age = max(0, mono - self.wait_starts[station]) if station in self.wait_starts else 0
            metric("line_waiting_current_seconds", age if valid else "NaN", {"station": station})
            metric("line_waiting_seconds_total", self.wait_seconds[station], {"station": station}, "counter")
        for (machine, material), (warn, stop) in MATERIALS.items():
            for level, key in (("warning", warn), ("stop", stop)):
                if key is None:
                    continue
                labels = {"machine": machine, "material": material, "level": level}
                metric("line_material_active", current(state.get(key, 0)), labels)
                metric("line_material_seconds_total", self.material_seconds[(machine, material, level)], labels, "counter")
                metric("line_material_activations_total", self.material_events[(machine, material, level)], labels, "counter")
            metric("line_material_warning_lead_seconds", self.warning_leads.get((machine, material), "NaN") if valid else "NaN",
                   {"machine": machine, "material": material})
        for machine, prefix in (("AKL1", "Line1"), ("AKL2", "Line2")):
            metric("line_label_bypass_active", current(state.get(prefix + "_PassthroughMode", 0)), {"machine": machine})
        for name in BR_POSITIONS:
            good = bool(valid and self.position_valid.get(name))
            record = self.positions.get(name, {})
            metric("line_br_data_valid", int(good), {"station": name})
            metric("line_br_response_code", record.get("code", 0) if good else "NaN", {"station": name})
            metric("line_br_response_error", int(400 <= record.get("code", 0) <= 499) if good else -1, {"station": name})
            metric("line_br_box_present", int(bool(record.get("box_id"))) if good else -1, {"station": name})
            metric("line_br_decode_errors_total", self.decode_errors[name], {"station": name}, "counter")
            for group in ("ok", "error", "idle", "other"):
                metric("line_br_observations_total", self.response_counts[(name, group)], {"station": name, "result": group}, "counter")
        br6 = self.positions.get("BR06", {})
        metric("line_plausi_label_present", int(bool(br6.get("shipping_label"))) if valid and self.position_valid.get("BR06") else -1)
        metric("line_observed_box_increments_total", self.box_delta_total, kind="counter")
        metric("line_box_counter_discontinuities_total", self.box_discontinuities, kind="counter")
        metric("line_observed_seconds_total", self.covered_seconds, kind="counter")
        metric("line_daily_box_count_valid", int(valid and state.get("dnes_pocet_boxu", -1) >= 0))
        metric("line_new_box_signal", current(state.get("novy_box", 0)))
        return lines


monitor = LineMonitor()
