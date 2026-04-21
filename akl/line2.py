# =====================================================================
# Soubor   : akl/line2.py
# Účel     : AKL Line2 bity
# Autor    : Michal
# =====================================================================

import logging

log = logging.getLogger("akl.line2")


def read_akl_line2(data, last_data) -> None:
    """📡 Načte stav tiskárny AKL Line2 a aktualizuje last_data."""

    # -----------------------------------------------------------------
    # ✅ OCHRANA: kontrola minimální délky bufferu
    # Potřebujeme číst byte 44 => délka musí být alespoň 45 bajtů
    # -----------------------------------------------------------------
    if not data or len(data) <= 44:
        log.warning(
            f"⚠️ AKL Line2: buffer je příliš krátký "
            f"(očekáváno min. 45 B, aktuálně: {len(data) if data else 0} B)"
        )
        return

    # -----------------------------------------------------------------
    # ✅ Definice jednotlivých bitů v byte 44
    # (název metriky, číslo bitu)
    # -----------------------------------------------------------------
    keys = [
        ("Line2_SystemReady", 0),        # Byte 44.0: Stav systému (zapnuto)
        ("Line2_StartDispatch", 1),      # Byte 44.1: Zásilka připravena k odeslání
        ("Line2_PassthroughMode", 2),    # Byte 44.2: Mód průchodu (bez označení)
        ("Line2_LabelWarning", 3),       # Byte 44.3: Nízká zásoba štítků
        ("Line2_LabelOut", 4),           # Byte 44.4: Štítky zcela došly
        ("Line2_RibbonWarning", 5),      # Byte 44.5: Nízká zásoba stuhy
        ("Line2_RibbonOut", 6),          # Byte 44.6: Stuha zcela došla
    ]

    # -----------------------------------------------------------------
    # ✅ Načtení status byte pro AKL Line2
    # -----------------------------------------------------------------
    status = data[44]

    # -----------------------------------------------------------------
    # ✅ Zpracování všech definovaných bitů
    # Pokud se hodnota změnila, uložíme ji do last_data a zalogujeme
    # -----------------------------------------------------------------
    for key, bit in keys:
        stav = int(bool(status & (1 << bit)))

        if stav != last_data.get(key, -1):
            last_data[key] = stav
            log.info(f"📑 {key} = {stav}")