# =====================================================================
# Soubor   : smartlog/prostoje.py
# Účel     : Prostoje (start/stop + klasifikace + event do pending_prostoje)
# Autor    : Michal
# =====================================================================

import time
import logging

log = logging.getLogger("smartlog.prostoje")

# 📌 Uchovávání časů začátků prostojů
prostoj_start_time = {}


def read_prostoje(data, last_data, pending_prostoje) -> None:
    """📡 Načte hodnoty všech prostojů a ukládá je jako jednu metodu."""

    # -----------------------------------------------------------------
    # ✅ OCHRANA: kontrola minimální délky bufferu
    # Potřebujeme číst byte 62 => délka musí být alespoň 63 bajtů
    # -----------------------------------------------------------------
    if not data or len(data) <= 62:
        log.warning(
            f"⚠️ Prostoje: buffer je příliš krátký "
            f"(očekáváno min. 63 B, aktuálně: {len(data) if data else 0} B)"
        )
        return

    now = time.time()

    # -----------------------------------------------------------------
    # ✅ Definice jednotlivých prostojů v byte 62
    # -----------------------------------------------------------------
    keys = [
        ("prostoj1", 0),  # Byte 62.0
        ("prostoj2", 1),  # Byte 62.1
        ("prostoj3", 2),  # Byte 62.2
        ("prostoj4", 3),  # Byte 62.3
        ("prostoj5", 4),  # Byte 62.4
        ("prostoj6", 5),  # Byte 62.5
        ("prostoj7", 6),  # Byte 62.6
    ]

    prostoj_status = data[62]

    for key, bit in keys:
        value = int(bool(prostoj_status & (1 << bit)))

        # ✅ držíme i aktuální stav v last_data
        if value != last_data.get(key, -1):
            last_data[key] = value
            log.info(f"📌 {key} = {value}")

        # 🟢 Prostoj začal
        if value == 1 and key not in prostoj_start_time:
            prostoj_start_time[key] = now

        # 🔴 Prostoj skončil
        elif value == 0 and key in prostoj_start_time:
            start_time = prostoj_start_time.pop(key)
            end_time = now
            duration = end_time - start_time

            # kratší než 10 s ignorujeme
            if duration < 10:
                continue
            elif duration < 120:
                prostoj_type = "mikro"
            else:
                prostoj_type = "standard"

            pending_prostoje.append(
                {
                    "prostoj": key,
                    "start_timestamp": int(start_time),
                    "end_timestamp": int(end_time),
                    "duration": int(duration),
                    "type": prostoj_type,
                }
            )

            log.info(
                f"📌 {key} skončil. "
                f"Trval {duration / 60:.2f} min, typ: {prostoj_type}"
            )