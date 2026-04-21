# =====================================================================
# Soubor   : convSmartlog.py
# Účel     : Agregace smartlog modulů (info, váha, prostoje, BR, bezpečnost)
# Autor    : Michal
# =====================================================================

from smartlog.info import read_info  # ✅ Import čtení základních hodnot
from smartlog.vaha import read_vaha  # ✅ Import Čtení stavu váhy
from smartlog.prostoje import read_prostoje  # ✅ Import Čtení prostojů
from smartlog.brPozice import read_br_data  # ✅ Import čtení BR
from smartlog.bezpecnost import read_bezpecnost_smartlog  # ✅ Import bezpečnosti


def read_smartlog_data(data, last_data, pending_metrics, pending_prostoje) -> None:
    """ 📡 Načte všechny proměnné ze složky smartlog a aktualizuje data """
    read_info(data, last_data)  # ✅ Čtení hlavních hodnot
    read_vaha(data, last_data)  # ✅ Čtení váhy
    read_prostoje(data, last_data, pending_prostoje)  # ✅ Čtení prostojů
    read_br_data(data, last_data, pending_metrics)  # ✅ Čtení BR08
    read_bezpecnost_smartlog(data, last_data)  # ✅ Čtení bezpečnosti