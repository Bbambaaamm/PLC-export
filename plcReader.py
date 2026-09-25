# =====================================================================
# Soubor   : plcReader.py
# Účel     : Nepřetržité čtení dat z PLC a aktualizace sdílených struktur
# Autor    : Michal
# Poznámka : Neprovádí žádný export - jen aktualizuje last_data + fronty
# =====================================================================

import time
import logging
from typing import Optional

import snap7

from convSmartlog import read_smartlog_data
from convGebhardt import read_gebhardt_data
from convTeleskop import read_teleskop_data
from machRanpak import read_ranpak_data
from printAkl import read_akl_status

from config import (
    PLC_IP,
    DB_NUMBER,
    START_OFFSET,
    SIZE,
    PLC_READ_INTERVAL_SEC,
    PLC_RECONNECT_DELAY_SEC,
    PLC_MAX_SAMPLE_GAP_SEC,
)

# Sdílené struktury jsou v prometheus.py – importujeme je sem
from prometheus import (
    last_data,
    last_data_lock,
    pending_metrics,
    pending_prostoje,
)

from smartlog.prostoje import prostoj_start_time

log = logging.getLogger("plcReader")

# Metriky doby aktivních chybových stavů:
# klíč = název exportované metriky, hodnota = zdrojový stavový klíč (0/1)
ERROR_DURATION_METRICS = {
    "V10_error_active_seconds_total": "V10_bMachineError",
    "V20_error_active_seconds_total": "V20_bMachineError",
    "V10_bLidSupplyLowError_active_seconds_total": "V10_bLidSupplyLowError",
    "V10_bGlueSupplyLowError_active_seconds_total": "V10_bGlueSupplyLowError",
    "V20_bLidSupplyLowError_active_seconds_total": "V20_bLidSupplyLowError",
    "V20_bGlueSupplyLowError_active_seconds_total": "V20_bGlueSupplyLowError",
    "Line1_LabelOut_active_seconds_total": "Line1_LabelOut",
    "Line1_RibbonOut_active_seconds_total": "Line1_RibbonOut",
    "Line2_LabelOut_active_seconds_total": "Line2_LabelOut",
    "Line2_RibbonOut_active_seconds_total": "Line2_RibbonOut",
}


def update_error_active_durations(now: float) -> None:
    """
    now je monotónní čas; stav musí být z předchozího vzorku.
    ⏱️ Přičte čas do metrik *_active_seconds_total pro všechny sledované chyby.
    Volat pouze pod last_data_lock.
    """
    last_sample = last_data.get("errors_last_sample_timestamp")
    if last_sample is None:
        last_data["errors_last_sample_timestamp"] = now
        return

    delta = now - last_sample
    if delta < 0 or delta > PLC_MAX_SAMPLE_GAP_SEC:
        prostoj_start_time.clear()
        last_data["errors_last_sample_timestamp"] = now
        return

    for metric_key, state_key in ERROR_DURATION_METRICS.items():
        if int(last_data.get(state_key, 0)) == 1:
            last_data[metric_key] = float(last_data.get(metric_key, 0.0)) + delta

    last_data["errors_last_sample_timestamp"] = now


def connect_to_plc(retry_seconds: float = PLC_RECONNECT_DELAY_SEC) -> snap7.client.Client:
    """
    🔌 Připojení k PLC s opakováním.
    Vrací připojeného snap7 klienta.
    """
    plc = snap7.client.Client()

    while True:
        try:
            with last_data_lock:
                last_data["plc_reconnects_total"] = int(last_data.get("plc_reconnects_total", 0)) + 1
            log.info(f"🔌 Připojuji se k PLC {PLC_IP}...")
            plc.connect(PLC_IP, 0, 1)

            if plc.get_connected():
                log.info("✅ Úspěšně připojeno k PLC!")
                return plc

        except Exception as e:
            log.error(f"❌ Chyba připojení k PLC: {e}")

        log.info(f"🔄 Opakování připojení za {retry_seconds:.0f} sekundy...")
        time.sleep(retry_seconds)


def invalidate_plc_data() -> None:
    """Volat pod lockem: neznámý interval nesmí být dobou poruchy."""
    last_data["plc_data_valid"] = 0
    last_data["errors_last_sample_timestamp"] = None
    prostoj_start_time.clear()


def process_sample(data, wall_time: float, monotonic_time: float) -> None:
    """Publikuje pouze úplný DB snapshot. Volat pod last_data_lock."""
    if data is None or len(data) != SIZE:
        raise ValueError(f"Incomplete PLC buffer: expected {SIZE} bytes, got {len(data) if data is not None else 0}")
    # Integrujeme PŘED dekódováním: interval patří poslednímu známému stavu.
    update_error_active_durations(monotonic_time)
    read_smartlog_data(data, last_data, pending_metrics, pending_prostoje,
                       wall_time=wall_time, monotonic_time=monotonic_time)
    read_gebhardt_data(data, last_data)
    read_teleskop_data(data, last_data)
    read_ranpak_data(data, last_data)
    read_akl_status(data, last_data)
    last_data["plc_last_read_timestamp"] = wall_time
    last_data["plc_poll_count"] += 1
    last_data["plc_data_valid"] = 1


def read_plc_data() -> None:
    """
    📡 Hlavní smyčka:
    - drží připojení k PLC
    - čte DB blok
    - volá konverzní moduly, které aktualizují last_data a fronty
    """
    plc: Optional[snap7.client.Client] = None
    while True:
        try:
            if plc is None or not plc.get_connected():
                with last_data_lock:
                    invalidate_plc_data()
                if plc is not None:
                    try:
                        plc.disconnect()
                    except Exception:
                        log.warning("PLC disconnect failed", exc_info=True)
                plc = connect_to_plc()

            data = plc.db_read(DB_NUMBER, START_OFFSET, SIZE)
            now = time.time()
            monotonic_now = time.monotonic()
            with last_data_lock:
                process_sample(data, now, monotonic_now)
            time.sleep(PLC_READ_INTERVAL_SEC)

        except Exception:
            log.exception("PLC read/processing failed")
            with last_data_lock:
                last_data["plc_read_errors_total"] += 1
                invalidate_plc_data()
            try:
                if plc is not None:
                    plc.disconnect()
            except Exception:
                log.warning("PLC disconnect failed", exc_info=True)
            plc = None
            time.sleep(PLC_RECONNECT_DELAY_SEC)
