# =====================================================================
# Soubor   : smartlog/bezpecnost.py
# Účel     : ESTOP tlačítka Smartlog
# Autor    : Michal
# =====================================================================

import logging

log = logging.getLogger("smartlog.bezpecnost")


def read_bezpecnost_smartlog(data, last_data) -> None:
    """📡 Načte stav ESTOP tlačítek Smartlog a aktualizuje last_data."""

    # -----------------------------------------------------------------
    # ✅ OCHRANA: kontrola minimální délky bufferu
    # Potřebujeme číst byty 64 a 65 => délka musí být alespoň 66 bajtů
    # -----------------------------------------------------------------
    if not data or len(data) <= 65:
        log.warning(
            f"⚠️ Smartlog bezpečnost: buffer je příliš krátký "
            f"(očekáváno min. 66 B, aktuálně: {len(data) if data else 0} B)"
        )
        return

    # -----------------------------------------------------------------
    # ✅ ESTOP tlačítka Smartlog - Byte 64
    # -----------------------------------------------------------------
    keys_byte_64 = [
        ("aktivovanoTlacitko_ES_TOP1", 0),  # Byte 64.0: ESTOP na hlavním rozvaděči
        ("aktivovanoTlacitko_ES_TOP2", 1),  # Byte 64.1: ESTOP za Ranpak V10
        ("aktivovanoTlacitko_ES_TOP3", 2),  # Byte 64.2: ESTOP v zatáčce za Plausicheck
        ("aktivovanoTlacitko_ES_TOP4", 3),  # Byte 64.3: ESTOP na konci dopravníku
        ("aktivovanoTlacitko_ES_TOP5", 4),  # Byte 64.4: ESTOP na kleci AKL
        ("aktivovanoTlacitko_ES_TOP6", 5),  # Byte 64.5: ESTOP na podružném rozvaděči =RP
        ("aktivovanoTlacitko_ES_TOP7", 6),  # Byte 64.6: ESTOP na začátku dopravníku SMARTLOG
        ("aktivovanoTlacitko_ES_TOP8", 7),  # Byte 64.7: ESTOP u váhy
    ]

    status_64 = data[64]

    for key, bit in keys_byte_64:
        new_value = int(bool(status_64 & (1 << bit)))

        if new_value != last_data.get(key, -1):
            last_data[key] = new_value
            log.info(f"🛑 {key} = {new_value}")

    # -----------------------------------------------------------------
    # ✅ ESTOP tlačítka Smartlog - Byte 65
    # -----------------------------------------------------------------
    keys_byte_65 = [
        ("aktivovanoTlacitko_ES_TOP9", 0),   # Byte 65.0: ESTOP na levém teleskopu (T1)
        ("aktivovanoTlacitko_ES_TOP10", 1),  # Byte 65.1: ESTOP na pravém teleskopu (T2)
    ]

    status_65 = data[65]

    for key, bit in keys_byte_65:
        new_value = int(bool(status_65 & (1 << bit)))

        if new_value != last_data.get(key, -1):
            last_data[key] = new_value
            log.info(f"🛑 {key} = {new_value}")