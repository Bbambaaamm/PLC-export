# =====================================================================
# Soubor   : ranpak/V10.py
# Účel     : Ranpak V10 bity
# Autor    : Michal
# =====================================================================

import logging

log = logging.getLogger("ranpak.V10")


def read_V10(data, last_data) -> None:
    """📦 Načte stav balicího stroje Ranpak V10 a aktualizuje last_data."""

    # -----------------------------------------------------------------
    # ✅ OCHRANA: kontrola minimální délky bufferu
    # Potřebujeme číst byte 28 => délka musí být alespoň 29 bajtů
    # -----------------------------------------------------------------
    if not data or len(data) <= 28:
        log.warning(
            f"⚠️ Ranpak V10: buffer je příliš krátký "
            f"(očekáváno min. 29 B, aktuálně: {len(data) if data else 0} B)"
        )
        return

    # -----------------------------------------------------------------
    # ✅ Definice jednotlivých bitů v byte 28
    # (název metriky, číslo bitu)
    # -----------------------------------------------------------------
    keys = [
        ("V10_bReadyToReceiveBox", 0),   # Byte 28.0: RTR - box je možné přijmout
        ("V10_bReadyToSendBox", 1),      # Byte 28.1: Box je připraven k odeslání
        ("V10_bMachineError", 2),        # Byte 28.2: Stroj v chybovém stavu
        ("V10_bLidSupplyLow", 3),        # Byte 28.3: Nízká zásoba vík
        ("V10_bLidSupplyLowError", 4),   # Byte 28.4: Kriticky nízká zásoba vík
        ("V10_bGlueSupplyLowError", 5),  # Byte 28.5: Kriticky nízká zásoba lepidla
        ("V10_safetyReady", 6),          # Byte 28.6: Stroj je bezpečně připraven
    ]

    # -----------------------------------------------------------------
    # ✅ Načtení status byte pro Ranpak V10
    # -----------------------------------------------------------------
    status = data[28]
    last_data["V10_status_byte_raw"] = status

    previous_status = last_data.get("V10_status_byte_last", -1)
    if previous_status != -1 and previous_status != status:
        last_data["V10_status_changes_total"] = int(last_data.get("V10_status_changes_total", 0)) + 1
    last_data["V10_status_byte_last"] = status

    # -----------------------------------------------------------------
    # ✅ Zpracování všech definovaných bitů
    # Pokud se hodnota změnila, uložíme ji do last_data a zalogujeme
    # -----------------------------------------------------------------
    for key, bit in keys:
        stav = int(bool(status & (1 << bit)))

        if stav != last_data.get(key, -1):
            last_data[key] = stav
            log.info(f"📦 {key} = {stav}")
