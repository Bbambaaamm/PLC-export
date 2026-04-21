# =====================================================================
# Soubor   : config.py
# Účel     : Konfigurace PLC připojení + základní konstanty
# Autor    : Michal
# =====================================================================

import os


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
