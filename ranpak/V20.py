# =====================================================================
# Soubor   : ranpak/V20.py
# Účel     : Ranpak V20 bity
# Autor    : Michal
# =====================================================================

import logging

log = logging.getLogger("ranpak.V20")


def read_V20(data, last_data) -> None:
    """📦 Načte stav balicího stroje Ranpak V20 a aktualizuje last_data."""

    # -----------------------------------------------------------------
    # ✅ OCHRANA: kontrola minimální délky bufferu
    # Potřebujeme číst byte 30 => délka musí být alespoň 31 bajtů
    # -----------------------------------------------------------------
    if not data or len(data) <= 30:
        log.warning(
            f"⚠️ Ranpak V20: buffer je příliš krátký "
            f"(očekáváno min. 31 B, aktuálně: {len(data) if data else 0} B)"
        )
        return

    # -----------------------------------------------------------------
    # ✅ Definice jednotlivých bitů v byte 30
    # (název metriky, číslo bitu)
    # -----------------------------------------------------------------
    keys = [
        ("V20_bReadyToReceiveBox", 0),   # Byte 30.0: RTR - box je možné přijmout
        ("V20_bReadyToSendBox", 1),      # Byte 30.1: Box je připraven k odeslání
        ("V20_bMachineError", 2),        # Byte 30.2: Stroj v chybovém stavu
        ("V20_bLidSupplyLow", 3),        # Byte 30.3: Nízká zásoba vík
        ("V20_bLidSupplyLowError", 4),   # Byte 30.4: Kriticky nízká zásoba vík
        ("V20_bGlueSupplyLowError", 5),  # Byte 30.5: Kriticky nízká zásoba lepidla
        ("V20_safetyReady", 6),          # Byte 30.6: Stroj je bezpečně připraven
    ]

    # -----------------------------------------------------------------
    # ✅ Načtení status byte pro Ranpak V20
    # -----------------------------------------------------------------
    status = data[30]

    # -----------------------------------------------------------------
    # ✅ Zpracování všech definovaných bitů
    # Pokud se hodnota změnila, uložíme ji do last_data a zalogujeme
    # -----------------------------------------------------------------
    for key, bit in keys:
        stav = int(bool(status & (1 << bit)))

        if stav != last_data.get(key, -1):
            last_data[key] = stav
            log.info(f"📦 {key} = {stav}")