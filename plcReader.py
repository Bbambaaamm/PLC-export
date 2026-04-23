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
    EXCEL_REFRESH_INTERVAL_SEC,
)

# Sdílené struktury jsou v prometheus.py – importujeme je sem
from prometheus import (
    last_data,
    last_data_lock,
    pending_metrics,
    pending_prostoje,
)

from dataExcelImport.dataImport import get_target_pocet_boxu, read_excel_data

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
    ⏱️ Přičte čas do metrik *_active_seconds_total pro všechny sledované chyby.
    Volat pouze pod last_data_lock.
    """
    last_sample = float(last_data.get("errors_last_sample_timestamp", 0.0) or 0.0)
    if last_sample <= 0:
        last_data["errors_last_sample_timestamp"] = now
        return

    delta = max(0.0, now - last_sample)
    if delta <= 0:
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


def load_excel_data() -> Optional[object]:
    """
    📂 Načte Excel data.
    Vrátí DataFrame (nebo cokoliv, co read_excel_data vrací), nebo None.
    """
    try:
        df = read_excel_data()
        log.info("📂 Excel načten úspěšně.")
        return df
    except FileNotFoundError as e:
        log.warning(f"⚠️ Excel nenalezen, pokračuji bez něj: {e}")
        return None
    except Exception as e:
        log.error(f"❌ Chyba při načítání Excelu, pokračuji bez něj: {e}")
        return None


def read_plc_data() -> None:
    """
    📡 Hlavní smyčka:
    - drží připojení k PLC
    - čte DB blok
    - volá konverzní moduly, které aktualizují last_data a fronty
    - ošetří Excel target
    """
    plc: Optional[snap7.client.Client] = None
    df = None
    last_excel_reload = 0.0

    # Heartbeat (důkaz, že smyčka běží i když se hodnoty nemění)
    poll_count = 0
    last_heartbeat = 0.0

    while True:
        try:
            # 1) Připojení / reconnect
            if plc is None or not plc.get_connected():
                if plc is not None:
                    log.warning("⚠️ Spojení s PLC ztraceno, připojuji znovu...")
                plc = connect_to_plc()

            # 2) Čtení dat
            data = plc.db_read(DB_NUMBER, START_OFFSET, SIZE)
            if not data:
                log.warning("⚠️ PLC vrátilo prázdná data.")
                time.sleep(1)
                continue

            # Heartbeat každých 5 s
            poll_count += 1
            now = time.time()
            if now - last_heartbeat >= 5:
                last_heartbeat = now
                log.info(f"💓 PLC heartbeat: poll_count={poll_count}")

            # 3) Periodický reload Excelu (např. kvůli změně dne/plánu).
            if (df is None) or (now - last_excel_reload >= EXCEL_REFRESH_INTERVAL_SEC):
                new_df = load_excel_data()
                if new_df is not None:
                    df = new_df
                    last_excel_reload = now
                elif df is None:
                    # Při úplném startu bez Excelu jen čekáme na další pokus.
                    last_excel_reload = now

            # 4) Target z Excelu – MIMO LOCK (aby neblokoval /metrics)
            target = []
            if df is not None:
                try:
                    target = get_target_pocet_boxu(df) or []
                except Exception as e:
                    log.error(f"❌ Chyba get_target_pocet_boxu(): {e}")
                    target = []

            # 5) Zpracování dat – LOCK držíme co nejkratší dobu
            with last_data_lock:
                # Smartlog (včetně BR08 + prostoje)
                read_smartlog_data(data, last_data, pending_metrics, pending_prostoje)

                # Gebhardt
                read_gebhardt_data(data, last_data)

                # Teleskopy
                read_teleskop_data(data, last_data)

                # Ranpak
                read_ranpak_data(data, last_data)

                # AKL
                read_akl_status(data, last_data)

                # Kumulativní doby aktivních chybových stavů
                update_error_active_durations(now)

                # Target uložit až teď
                last_data["target_pocet_boxu"] = target
                last_data["plc_last_read_timestamp"] = now
                last_data["plc_poll_count"] = poll_count

            time.sleep(PLC_READ_INTERVAL_SEC)

        except Exception:
            # stacktrace do logu (aby bylo jasné, co to shodilo)
            log.exception("❌ Chyba čtení PLC (stacktrace):")
            with last_data_lock:
                last_data["plc_read_errors_total"] = int(last_data.get("plc_read_errors_total", 0)) + 1

            # vynutit reconnect v dalším kole
            try:
                if plc is not None:
                    plc.disconnect()
            except Exception:
                pass
            plc = None

            time.sleep(PLC_RECONNECT_DELAY_SEC)
