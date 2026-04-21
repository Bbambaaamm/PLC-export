# =====================================================================
# Soubor   : convGebhardt.py
# Účel     : Agregace Gebhardt modulů
# Autor    : Michal
# =====================================================================

from gebhardt.chodPohonu import read_chod_pohonu  # ✅ Čtení pohonů
from gebhardt.bezpecnost import read_bezpecnost  # ✅ Čtení bezpečnostních tlačítek


def read_gebhardt_data(data, last_data) -> None:
    """ 📡 Načte všechny Gebhardt hodnoty a aktualizuje data """
    read_chod_pohonu(data, last_data)  # ✅ Čtení stavu pohonů
    read_bezpecnost(data, last_data)   # ✅ Čtení bezpečnostních tlačítek