# =====================================================================
# Soubor   : akl/line1.py
# Účel     : AKL Line1 bity
# Autor    : Michal
# =====================================================================

import logging

log = logging.getLogger("akl.line1")


def read_akl_line1(data, last_data) -> None:
    """📡 Načte stav tiskárny AKL Line1 a aktualizuje last_data."""

    # -----------------------------------------------------------------
    # ✅ OCHRANA: kontrola minimální délky bufferu
    # Potřebujeme číst byte 42 => délka musí být alespoň 43 bajtů
    # -----------------------------------------------------------------
    if not data or len(data) <= 42:
        log.warning(
            f"⚠️ AKL Line1: buffer je příliš krátký "
            f"(očekáváno min. 43 B, aktuálně: {len(data) if data else 0} B)"
        )
        return

    # -----------------------------------------------------------------
    # ✅ Definice jednotlivých bitů v byte 42
    # (název metriky, číslo bitu)
    # -----------------------------------------------------------------
    keys = [
        ("Line1_SystemReady", 0),        # Byte 42.0: Stav systému (zapnuto)
        ("Line1_StartDispatch", 1),      # Byte 42.1: Zásilka připravena k odeslání
        ("Line1_PassthroughMode", 2),    # Byte 42.2: Mód průchodu (bez označení)
        ("Line1_LabelWarning", 3),       # Byte 42.3: Nízká zásoba štítků
        ("Line1_LabelOut", 4),           # Byte 42.4: Štítky zcela došly
        ("Line1_RibbonWarning", 5),      # Byte 42.5: Nízká zásoba stuhy
        ("Line1_RibbonOut", 6),          # Byte 42.6: Stuha zcela došla
    ]

    # -----------------------------------------------------------------
    # ✅ Načtení status byte pro AKL Line1
    # -----------------------------------------------------------------
    status = data[42]

    # -----------------------------------------------------------------
    # ✅ Zpracování všech definovaných bitů
    # Pokud se hodnota změnila, uložíme ji do last_data a zalogujeme
    # -----------------------------------------------------------------
    for key, bit in keys:
        stav = int(bool(status & (1 << bit)))

        if stav != last_data.get(key, -1):
            last_data[key] = stav
            log.info(f"📑 {key} = {stav}")
