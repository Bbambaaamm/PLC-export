"""Obnova plánu mimo PLC vlákno; stejný interval pro úspěch i chybu."""

import logging
import time

from config import EXCEL_REFRESH_INTERVAL_SEC
from dataExcelImport.dataImport import read_excel_data, get_target_pocet_boxu
from prometheus import last_data, last_data_lock

log = logging.getLogger("excelReader")


def refresh_excel_targets() -> None:
    try:
        target = get_target_pocet_boxu(read_excel_data())
        with last_data_lock:
            last_data["target_pocet_boxu"] = target
            last_data["excel_last_reload_timestamp"] = time.time()
            last_data["excel_data_valid"] = 1
    except Exception:
        log.warning("Excel refresh failed; retaining last plan", exc_info=True)
        with last_data_lock:
            last_data["excel_data_valid"] = 0
            last_data["excel_read_errors_total"] += 1


def read_excel_targets() -> None:
    while True:
        refresh_excel_targets()
        time.sleep(EXCEL_REFRESH_INTERVAL_SEC)
