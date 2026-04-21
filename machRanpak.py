# =====================================================================
# Soubor   : machRanpak.py
# Účel     : Agregace Ranpak modulů (V10, V20)
# Autor    : Michal
# =====================================================================

from ranpak.V10 import read_V10
from ranpak.V20 import read_V20


def read_ranpak_data(data, last_data) -> None:
    """ 📦 Načte všechny hodnoty pro Ranpak stroje (V10 a V20) a aktualizuje `last_data` """
    read_V10(data, last_data)
    read_V20(data, last_data)