# =====================================================================
# Soubor   : smartlog/brPozice.py
# Účel     : Agregace BR modulů
# Autor    : Michal
# =====================================================================

from smartlog.br.br08 import read_br08


def read_br_data(data, last_data, pending_metrics) -> None:
    """📡 Načte všechny BR hodnoty a aktualizuje data."""

    # -----------------------------------------------------------------
    # ✅ Čtení BR08
    # Tento krok zahrnuje:
    # - box_id
    # - kod_odpovedi
    # - smer_vytrideni
    # -----------------------------------------------------------------
    read_br08(data, last_data, pending_metrics)

    # -----------------------------------------------------------------
    # 📌 Sem lze v budoucnu přidat další BR moduly:
    # read_br09(data, last_data, pending_metrics)
    # read_br10(data, last_data, pending_metrics)
    # -----------------------------------------------------------------