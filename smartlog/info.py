# =====================================================================
# Soubor   : smartlog/info.py
# Účel     : dnes_pocet_boxu + smartlog_zapnut
# Autor    : Michal
# =====================================================================

import struct
import logging

log = logging.getLogger("smartlog.info")


def read_info(data, last_data) -> None:
    """📡 Čte a aktualizuje hodnoty dnes_pocet_boxu a smartlog_zapnut."""

    # -----------------------------------------------------------------
    # ✅ OCHRANA: kontrola minimální délky bufferu
    # Potřebujeme číst:
    # - byte 56
    # - bytes 58:60
    # => délka musí být alespoň 60 bajtů
    # -----------------------------------------------------------------
    if not data or len(data) < 60:
        log.warning(
            f"⚠️ Smartlog info: buffer je příliš krátký "
            f"(očekáváno min. 60 B, aktuálně: {len(data) if data else 0} B)"
        )
        return

    # -----------------------------------------------------------------
    # ✅ Čtení dnes_pocet_boxu (INT / 2B, big-endian)
    # -----------------------------------------------------------------
    dnes_pocet_boxu = struct.unpack(">h", data[58:60])[0]

    if dnes_pocet_boxu != last_data.get("dnes_pocet_boxu", -1):
        last_data["dnes_pocet_boxu"] = dnes_pocet_boxu
        log.info(f"✅ dnes_pocet_boxu = {dnes_pocet_boxu}")

    # -----------------------------------------------------------------
    # ✅ Čtení smartlog_zapnut (Byte 56.0)
    # -----------------------------------------------------------------
    smartlog_zapnut = int(bool(data[56] & (1 << 0)))

    if smartlog_zapnut != last_data.get("smartlog_zapnut", -1):
        last_data["smartlog_zapnut"] = smartlog_zapnut
        log.info(f"✅ smartlog_zapnut = {smartlog_zapnut}")