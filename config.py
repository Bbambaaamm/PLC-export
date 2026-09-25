# =====================================================================
# Soubor   : config.py
# Účel     : Konfigurace PLC připojení + základní konstanty
# Autor    : Michal
# =====================================================================

import os
import math


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


# 📌 Nastavení připojení k PLC
PLC_IP = os.getenv("PLC_IP", "10.40.36.2")
DB_NUMBER = _get_env_int("PLC_DB_NUMBER", 2000)
START_OFFSET = _get_env_int("PLC_START_OFFSET", 0)
SIZE = _get_env_int("PLC_DB_SIZE", 8122)  # Velikost datablocku

# 📌 Intervaly
PLC_READ_INTERVAL_SEC = _get_env_float("PLC_READ_INTERVAL_SEC", 0.5)
PLC_RECONNECT_DELAY_SEC = _get_env_float("PLC_RECONNECT_DELAY_SEC", 2.0)
EXCEL_REFRESH_INTERVAL_SEC = _get_env_float("EXCEL_REFRESH_INTERVAL_SEC", 300.0)
PLC_MAX_SAMPLE_GAP_SEC = _get_env_float(
    "PLC_MAX_SAMPLE_GAP_SEC", max(5.0, 3 * PLC_READ_INTERVAL_SEC)
)

# Dekodéry používají absolutní offsety DB, nejvyšší čtený byte je 3650.
if START_OFFSET != 0 or SIZE < 3651:
    raise ValueError("PLC_START_OFFSET must be 0 and PLC_DB_SIZE must be >= 3651")
for name in ("PLC_READ_INTERVAL_SEC", "PLC_RECONNECT_DELAY_SEC",
             "EXCEL_REFRESH_INTERVAL_SEC", "PLC_MAX_SAMPLE_GAP_SEC"):
    value = globals()[name]
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
