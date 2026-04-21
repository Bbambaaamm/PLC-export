# =====================================================================
# Soubor   : config.py
# Účel     : Konfigurace PLC připojení + základní konstanty
# Autor    : Michal
# =====================================================================

# 📌 Nastavení připojení k PLC
PLC_IP = "10.40.36.2"
DB_NUMBER = 2000
START_OFFSET = 0
SIZE = 8122  # Velikost datablocku

# 📌 Intervaly
PLC_READ_INTERVAL_SEC = 0.5
PLC_RECONNECT_DELAY_SEC = 2.0