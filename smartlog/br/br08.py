# =====================================================================
# Soubor   : smartlog/br/br08.py
# Účel     : BR08 průjezdy (BoxID + kod odpovedi + smer vytrideni)
# Autor    : Michal
# =====================================================================

import time
import logging

from prometheus import br08_prefix_counters

log = logging.getLogger("smartlog.br08")


def read_br08(data, last_data, pending_metrics, executed_timestamp=None) -> None:
    """📡 Načte BR08 (čte ID balíků) a aktualizuje průjezdy včetně update kodu/směru."""

    # -----------------------------------------------------------------
    # ✅ OCHRANA: kontrola minimální délky bufferu
    # -----------------------------------------------------------------
    if not data or len(data) < 3651:
        log.warning(
            f"⚠️ BR08: buffer je příliš krátký pro čtení dat "
            f"(očekáváno min. 3651 B, aktuálně: {len(data) if data else 0} B)"
        )
        return

    # -----------------------------------------------------------------
    # ✅ BoxID
    # -----------------------------------------------------------------
    try:
        box_id = data[3534:3546].decode("ascii", errors="ignore").replace("\x00", "").strip()
    except Exception as e:
        log.warning(f"⚠️ BR08: chyba při dekódování box_id: {e}")
        return

    if not box_id:
        return

    # -----------------------------------------------------------------
    # ✅ RAW data
    # kod_odpovedi = INT @ 3648.0 (2B)
    # smer_vytrideni = SINT @ 3650.0 (1B)
    # -----------------------------------------------------------------
    raw_kod = data[3648:3650]
    raw_smer = data[3650:3651]

    kod_odpovedi = int.from_bytes(raw_kod, byteorder="big", signed=True)
    smer_vytrideni = int.from_bytes(raw_smer, byteorder="little", signed=True)

    timestamp = int(time.time())

    # -----------------------------------------------------------------
    # ✅ Diagnostika pouze při změně RAW stavu
    # -----------------------------------------------------------------
    last_raw = last_data.get("br08_last_raw", {})

    current_raw = {
        "box_id": box_id,
        "raw_kod": raw_kod.hex(),
        "raw_smer": raw_smer.hex(),
        "kod_odpovedi": kod_odpovedi,
        "smer_vytrideni": smer_vytrideni,
    }

    if current_raw != last_raw:
        log.info(
            f"🔍 BR08 RAW: box_id={box_id}, raw_kod={raw_kod.hex()}, "
            f"kod_odpovedi={kod_odpovedi}, raw_smer={raw_smer.hex()}, "
            f"smer_vytrideni={smer_vytrideni}"
        )

    last_data["br08_last_raw"] = current_raw

    # -----------------------------------------------------------------
    # ✅ Pokud je dotaz spuštěn ručně, použijeme executed_timestamp
    # -----------------------------------------------------------------
    if executed_timestamp is not None:
        if any(
            entry.get("box_id") == box_id and int(entry.get("timestamp", 0)) >= int(executed_timestamp)
            for entry in pending_metrics
        ):
            return

    # -----------------------------------------------------------------
    # ✅ Stav resetu PLC
    # -----------------------------------------------------------------
    is_reset_state = (kod_odpovedi == 0 and smer_vytrideni == 0)

    # -----------------------------------------------------------------
    # ✅ Najdi existující záznam boxu
    # -----------------------------------------------------------------
    existing = None
    for entry in reversed(last_data.get("br08_prujezdy", [])):
        if entry.get("box_id") == box_id:
            existing = entry
            break

    # -----------------------------------------------------------------
    # ✅ Paměť, že reset daného boxu už byl jednou ignorován
    # -----------------------------------------------------------------
    ignored_reset_box_id = last_data.get("br08_ignored_reset_box_id")

    if existing is not None:
        old_kod = existing.get("kod_odpovedi")
        old_smer = existing.get("smer_vytrideni")

        if old_kod == kod_odpovedi and old_smer == smer_vytrideni:
            return

        if is_reset_state and not (old_kod == 0 and old_smer == 0):
            if ignored_reset_box_id != box_id:
                log.info(
                    f"⏭️ BR08 reset ignorován: {box_id}, "
                    f"ponechán kod_odpovedi={old_kod}, smer_vytrideni={old_smer}"
                )
                last_data["br08_ignored_reset_box_id"] = box_id
            return

        if not is_reset_state:
            last_data["br08_ignored_reset_box_id"] = None

        existing["timestamp"] = timestamp
        existing["kod_odpovedi"] = kod_odpovedi
        existing["smer_vytrideni"] = smer_vytrideni

        if not any(
            e.get("box_id") == box_id
            and e.get("kod_odpovedi") == kod_odpovedi
            and e.get("smer_vytrideni") == smer_vytrideni
            for e in pending_metrics
        ):
            pending_metrics.append(
                {
                    "box_id": box_id,
                    "timestamp": timestamp,
                    "kod_odpovedi": kod_odpovedi,
                    "smer_vytrideni": smer_vytrideni,
                }
            )

        log.info(
            f"♻️ BR08 update: {box_id}, čas: {timestamp}, "
            f"kod_odpovedi: {old_kod}→{kod_odpovedi}, "
            f"smer_vytrideni: {old_smer}→{smer_vytrideni}"
        )
        return

    if is_reset_state:
        return

    last_data["br08_ignored_reset_box_id"] = None

    last_data.setdefault("br08_prujezdy", []).append(
        {
            "box_id": box_id,
            "timestamp": timestamp,
            "kod_odpovedi": kod_odpovedi,
            "smer_vytrideni": smer_vytrideni,
        }
    )

    if not any(
        entry.get("box_id") == box_id
        and entry.get("kod_odpovedi") == kod_odpovedi
        and entry.get("smer_vytrideni") == smer_vytrideni
        for entry in pending_metrics
    ):
        pending_metrics.append(
            {
                "box_id": box_id,
                "timestamp": timestamp,
                "kod_odpovedi": kod_odpovedi,
                "smer_vytrideni": smer_vytrideni,
            }
        )

    prefix = box_id[:2]
    if prefix in br08_prefix_counters:
        br08_prefix_counters[prefix] += 1

    log.info(
        f"📌 BR08 průjezd: {box_id}, čas: {timestamp}, "
        f"kod_odpovedi: {kod_odpovedi}, smer_vytrideni: {smer_vytrideni}"
    )
