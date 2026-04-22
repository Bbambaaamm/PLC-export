# =====================================================================
# Soubor   : dataExcelImport/dataImport.py
# Účel     : Načtení KPI dat z plánovacího Excelu
# Autor    : Codex
# =====================================================================

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import pandas as pd


DEFAULT_EXCEL_PATH = (
    r"I:\Bor\11-Operative\02-ZooRoyal\07-Key Account Rewe Digital\Kapa Planung"
)


def _resolve_excel_file(path: str | None = None) -> Path:
    """
    Vrátí konkrétní excelový soubor.

    Podporuje:
    - přímou cestu na soubor
    - cestu na složku (vezme nejnovější xls/xlsx/xlsm)
    """
    raw_path = path or os.getenv("KPI_EXCEL_PATH", DEFAULT_EXCEL_PATH)
    source = Path(raw_path)

    if source.is_file():
        return source

    if source.is_dir():
        candidates: list[Path] = []
        for suffix in ("*.xlsx", "*.xlsm", "*.xls"):
            candidates.extend(source.glob(suffix))

        if not candidates:
            raise FileNotFoundError(f"Ve složce nejsou excelové soubory: {source}")

        # Nejnovější soubor dle času změny.
        return max(candidates, key=lambda p: p.stat().st_mtime)

    raise FileNotFoundError(f"Excel cesta neexistuje: {source}")


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _normalize_date(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    return parsed.dt.date


def read_excel_data(path: str | None = None) -> pd.DataFrame:
    """
    Načte KPI tabulku a vrátí očištěný DataFrame.

    Očekávané sloupce podle pozice:
      A  = datum
      M  = Prognose erledigte Aufträge
      N  = Prognose erledigte Pakete
      O  = Prognose erledigte Teile
      Q  = Erledigte Aufträge
      R  = Erledigte Pakete
      S  = Erledigte Teile
    """
    excel_file = _resolve_excel_file(path)

    raw_df = pd.read_excel(excel_file)
    required_idx = [0, 12, 13, 14, 16, 17, 18]

    if raw_df.shape[1] <= max(required_idx):
        raise ValueError(
            "Excel nemá očekávané sloupce A/M/N/O/Q/R/S "
            f"(nalezeno {raw_df.shape[1]} sloupců)."
        )

    df = raw_df.iloc[:, required_idx].copy()
    df.columns = [
        "datum",
        "prognose_auftrage",
        "prognose_pakete",
        "prognose_teile",
        "erledigte_auftrage",
        "erledigte_pakete",
        "erledigte_teile",
    ]

    df["datum"] = _normalize_date(df["datum"])

    for col in df.columns:
        if col != "datum":
            df[col] = _to_numeric(df[col])

    # Odstraníme prázdné řádky (bez data nebo bez všech KPI hodnot).
    kpi_cols = [c for c in df.columns if c != "datum"]
    df = df[df["datum"].notna()]
    df = df[df[kpi_cols].notna().any(axis=1)]

    # Pro stejné datum necháme poslední neprázdný záznam.
    df = df.drop_duplicates(subset=["datum"], keep="last")

    return df.reset_index(drop=True)


def get_target_pocet_boxu(df: pd.DataFrame) -> list[tuple[str, float]]:
    """
    Vrátí dvojice (datum, prognóza balíků/boxů) pro metriky.

    Poznámka:
    - "boxy" mapujeme na sloupec N: Prognose erledigte Pakete.
    - skutečný výkon (Q/R/S) je ve vráceném DataFrame z read_excel_data(),
      typicky vyplněný pro předchozí den.
    """
    if df is None or df.empty:
        return []

    work = df[["datum", "prognose_pakete"]].dropna(subset=["datum", "prognose_pakete"])

    target: list[tuple[str, float]] = []
    for row in work.itertuples(index=False):
        datum = row.datum.isoformat() if hasattr(row.datum, "isoformat") else str(row.datum)
        # Počet boxů je celočíselná KPI; Excel často drží podkladovou desetinnou
        # hodnotu (např. kvůli vzorci), ale v tabulce ji zobrazuje zaokrouhleně.
        target.append((datum, float(round(float(row.prognose_pakete)))))

    return target


def get_daily_kpi_rows(df: pd.DataFrame) -> list[dict]:
    """Pomocná funkce: vrátí kompletní KPI řádky jako list slovníků."""
    if df is None or df.empty:
        return []

    def _records(data: pd.DataFrame) -> Iterable[dict]:
        for row in data.itertuples(index=False):
            yield {
                "datum": row.datum.isoformat() if hasattr(row.datum, "isoformat") else str(row.datum),
                "prognose_auftrage": row.prognose_auftrage,
                "prognose_pakete": row.prognose_pakete,
                "prognose_teile": row.prognose_teile,
                "erledigte_auftrage": row.erledigte_auftrage,
                "erledigte_pakete": row.erledigte_pakete,
                "erledigte_teile": row.erledigte_teile,
            }

    return list(_records(df))
