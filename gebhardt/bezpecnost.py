# =====================================================================
# Soubor   : gebhardt/bezpecnost.py
# Účel     : ESTOP tlačítka Gebhardt
# Autor    : Michal
# =====================================================================

import logging

log = logging.getLogger("gebhardt.bezpecnost")


def read_bezpecnost(data, last_data) -> None:
    """📡 Načte stav bezpečnostních tlačítek (ESTOP) a aktualizuje last_data."""

    # -----------------------------------------------------------------
    # ✅ OCHRANA: kontrola minimální délky bufferu
    # Potřebujeme číst byte 2 => délka musí být alespoň 3 bajty
    # -----------------------------------------------------------------
    if not data or len(data) <= 2:
        log.warning(
            f"⚠️ Bezpečnost: buffer je příliš krátký "
            f"(očekáváno min. 3 B, aktuálně: {len(data) if data else 0} B)"
        )
        return

    # -----------------------------------------------------------------
    # ✅ Definice jednotlivých ESTOP tlačítek v byte 2
    # -----------------------------------------------------------------
    bezpecnost_keys = [
        "aktivovanoTlacitko1",  # Byte 2.0
        "aktivovanoTlacitko2",  # Byte 2.1
        "aktivovanoTlacitko3",  # Byte 2.2
        "aktivovanoTlacitko4",  # Byte 2.3
        "aktivovanoTlacitko5",  # Byte 2.4
        "aktivovanoTlacitko6",  # Byte 2.5
    ]

    # -----------------------------------------------------------------
    # ✅ Načtení status byte pro bezpečnostní tlačítka
    # -----------------------------------------------------------------
    bezpecnost_status = data[2]

    # -----------------------------------------------------------------
    # ✅ Zpracování všech definovaných bitů
    # Pokud se hodnota změnila, uložíme ji do last_data a zalogujeme
    # -----------------------------------------------------------------
    for i, key in enumerate(bezpecnost_keys):
        stav = int(bool(bezpecnost_status & (1 << i)))

        if stav != last_data.get(key, -1):
            last_data[key] = stav
            log.info(f"⛔ {key} = {stav}")
