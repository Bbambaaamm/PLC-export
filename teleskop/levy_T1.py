# =====================================================================
# Soubor   : teleskop/levy_T1.py
# Účel     : Levý teleskop T1
# Autor    : Michal
# =====================================================================

import logging

log = logging.getLogger("teleskop.levy_T1")


def read_levy_T1(data, last_data) -> None:
    """📡 Čte hodnoty pro levý teleskop T1 a aktualizuje last_data."""

    # -----------------------------------------------------------------
    # ✅ OCHRANA: kontrola minimální délky bufferu
    # Potřebujeme číst byte 16 => délka musí být alespoň 17 bajtů
    # -----------------------------------------------------------------
    if not data or len(data) <= 16:
        log.warning(
            f"⚠️ Levý teleskop T1: buffer je příliš krátký "
            f"(očekáváno min. 17 B, aktuálně: {len(data) if data else 0} B)"
        )
        return

    # -----------------------------------------------------------------
    # ✅ Definice jednotlivých bitů v byte 16
    # -----------------------------------------------------------------
    keys = [
        ("safetyReady_levy_T1", 0),  # Byte 16.0: Bezpečnostní stav levého teleskopu
        ("pasChod_levy_T1", 1),      # Byte 16.1: Stav pohonu levého teleskopu
    ]

    # -----------------------------------------------------------------
    # ✅ Načtení status byte pro levý teleskop T1
    # -----------------------------------------------------------------
    status = data[16]

    # -----------------------------------------------------------------
    # ✅ Zpracování všech definovaných bitů
    # Pokud se hodnota změnila, uložíme ji do last_data a zalogujeme
    # -----------------------------------------------------------------
    for key, bit in keys:
        new_value = int(bool(status & (1 << bit)))

        if new_value != last_data.get(key, -1):
            last_data[key] = new_value
            log.info(f"⚙️ {key} = {new_value}")
