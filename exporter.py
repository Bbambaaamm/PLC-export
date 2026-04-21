# =====================================================================
# Soubor   : exporter.py
# Účel     : Start PLC reader thread + Prometheus exporter (Flask)
# Autor    : Michal
# Poznámka : Hlavní entrypoint aplikace
# =====================================================================

from threading import Thread
import logging
import os

from prometheus import start_prometheus
from plcReader import read_plc_data


def setup_logging() -> None:
    """
    Nastavení jednotného logování.
    - jasné timestampy a názvy modulů
    - možnost přepnout úroveň logu přes env: LOG_LEVEL=DEBUG/INFO/WARNING/ERROR
    """
    os.environ.setdefault("PYTHONUTF8", "1")

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


if __name__ == "__main__":
    setup_logging()
    log = logging.getLogger("exporter")

    log.info("-----------------------------------")
    log.info("🚀 Startuji služby...")
    log.info("-----------------------------------")

    log.info("🔄 Spouštím PLC čtení ve vlákně...")
    Thread(target=read_plc_data, name="PLCReader", daemon=True).start()

    log.info("🚀 Spouštím Prometheus exporter (Flask) ...")
    # Poznámka: tohle je exporter /metrics. Není to Prometheus server.
    start_prometheus()