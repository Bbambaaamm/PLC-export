# =====================================================================
# Soubor   : gebhardt/chodPohonu.py
# Účel     : Stav pohonů M1/M2
# Autor    : Michal
# =====================================================================

import logging

log = logging.getLogger("gebhardt.chodPohonu")


def read_chod_pohonu(data, last_data) -> None:
    """📡 Načte stav pohonů M1 a M2 a aktualizuje last_data."""

    # -----------------------------------------------------------------
    # ✅ OCHRANA: kontrola minimální délky bufferu
    # Potřebujeme číst byte 0 => délka musí být alespoň 1 bajt
    # -----------------------------------------------------------------
    if not data or len(data) <= 0:
        log.warning(
            f"⚠️ Chod pohonů: buffer je příliš krátký "
            f"(očekáváno min. 1 B, aktuálně: {len(data) if data else 0} B)"
        )
        return

    # -----------------------------------------------------------------
    # ✅ Definice jednotlivých bitů v byte 0
    # -----------------------------------------------------------------
    keys = [
        ("M1", 0, "Pohon 1"),  # Byte 0.0
        ("M2", 1, "Pohon 2"),  # Byte 0.1
    ]

    # -----------------------------------------------------------------
    # ✅ Načtení status byte pro pohony
    # -----------------------------------------------------------------
    status = data[0]

    # -----------------------------------------------------------------
    # ✅ Zpracování všech definovaných bitů
    # Pokud se hodnota změnila, uložíme ji do last_data a zalogujeme
    # -----------------------------------------------------------------
    for key, bit, popis in keys:
        stav = int(bool(status & (1 << bit)))

        if stav != last_data.get(key, -1):
            last_data[key] = stav
            log.info(f"⚙️ {key} ({popis}) = {stav}")