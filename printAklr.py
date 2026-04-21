# =====================================================================
# Soubor   : printAkl.py
# Účel     : Agregace AKL Line1 + Line2
# Autor    : Michal
# =====================================================================

from akl.line1 import read_akl_line1
from akl.line2 import read_akl_line2


def read_akl_status(data, last_data) -> None:
    """ 📡 Načte stav AKL Line1/Line2 a aktualizuje last_data """
    read_akl_line1(data, last_data)
    read_akl_line2(data, last_data)