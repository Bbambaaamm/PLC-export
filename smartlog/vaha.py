# =====================================================================
# Soubor   : smartlog/vaha.py
# Účel     : Stav váhy (chod)
# Autor    : Michal
# =====================================================================

import logging

log = logging.getLogger("smartlog.vaha")


def read_vaha(data, last_data) -> None:
    """📡 Načte stav váhy (chod) z PLC a uloží jej do last_data."""

    # -----------------------------------------------------------------
    # ✅ OCHRANA: kontrola minimální délky bufferu
    # Potřebujeme číst byte 66 => délka musí být alespoň 67 bajtů
    # -----------------------------------------------------------------
    if not data or len(data) <= 66:
        log.warning(
            f"⚠️ Váha: buffer je příliš krátký "
            f"(očekáváno min. 67 B, aktuálně: {len(data) if data else 0} B)"
        )
        return

    # -----------------------------------------------------------------
    # ✅ Definice bitů v byte 66
    # -----------------------------------------------------------------
    keys = [
        ("vahaChod", 0),  # Byte 66.0: Stav chodu váhy
    ]

    status = data[66]

    for key, bit in keys:
        new_value = int(bool(status & (1 << bit)))

        if new_value != last_data.get(key, -1):
            last_data[key] = new_value
            log.info(f"✅ {key} = {new_value}")