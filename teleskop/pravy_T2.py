# =====================================================================
# Soubor   : teleskop/pravy_T2.py
# Účel     : Pravý teleskop T2
# Autor    : Michal
# =====================================================================

import logging

log = logging.getLogger("teleskop.pravy_T2")


def read_pravy_T2(data, last_data) -> None:
    """📡 Čte hodnoty pro pravý teleskop T2 a aktualizuje last_data."""

    # -----------------------------------------------------------------
    # ✅ OCHRANA: kontrola minimální délky bufferu
    # Potřebujeme číst byte 14 => délka musí být alespoň 15 bajtů
    # -----------------------------------------------------------------
    if not data or len(data) <= 14:
        log.warning(
            f"⚠️ Pravý teleskop T2: buffer je příliš krátký "
            f"(očekáváno min. 15 B, aktuálně: {len(data) if data else 0} B)"
        )
        return

    # -----------------------------------------------------------------
    # ✅ Definice jednotlivých bitů v byte 14
    # -----------------------------------------------------------------
    keys = [
        ("safetyReady_pravy_T2", 0),  # Byte 14.0: Bezpečnostní stav pravého teleskopu
        ("pasChod_pravy_T2", 1),      # Byte 14.1: Stav pohonu pravého teleskopu
    ]

    # -----------------------------------------------------------------
    # ✅ Načtení status byte pro pravý teleskop T2
    # -----------------------------------------------------------------
    status = data[14]

    # -----------------------------------------------------------------
    # ✅ Zpracování všech definovaných bitů
    # Pokud se hodnota změnila, uložíme ji do last_data a zalogujeme
    # -----------------------------------------------------------------
    for key, bit in keys:
        new_value = int(bool(status & (1 << bit)))

        if new_value != last_data.get(key, -1):
            last_data[key] = new_value
            log.info(f"⚙️ {key} = {new_value}")