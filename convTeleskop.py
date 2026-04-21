# =====================================================================
# Soubor   : convTeleskop.py
# Účel     : Agregace teleskop modulů
# Autor    : Michal
# =====================================================================

from teleskop.levy_T1 import read_levy_T1  # ✅ Levý teleskop
from teleskop.pravy_T2 import read_pravy_T2  # ✅ Pravý teleskop


def read_teleskop_data(data, last_data) -> None:
    """ 📡 Načte všechny hodnoty pro teleskopy a aktualizuje last_data """
    read_levy_T1(data, last_data)
    read_pravy_T2(data, last_data)