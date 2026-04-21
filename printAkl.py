# =====================================================================
# Soubor   : printAkl.py
# Účel     : Kompatibilní import pro AKL agregaci
# Autor    : Michal
# Poznámka : Některé části projektu importují modul `printAkl`.
#            Implementace je ve `printAklr.py`, proto ji zde pouze
#            re-exportujeme, aby se předešlo chybě ModuleNotFoundError.
# =====================================================================

from printAklr import read_akl_status

__all__ = ["read_akl_status"]
