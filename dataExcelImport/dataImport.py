# =====================================================================
# Soubor   : dataExcelImport/dataImport.py
# Účel     : Načtení KPI dat z plánovacího Excelu bez pandas/numpy
# Autor    : Codex
# =====================================================================

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Iterator, Sequence


DEFAULT_EXCEL_PATH = (
    r"I:\\Bor\\11-Operative\\02-ZooRoyal\\07-Key Account Rewe Digital\\Kapa Planung"
)

KPI_COLUMNS = (
    "datum",
    "prognose_auftrage",
    "prognose_pakete",
    "prognose_teile",
    "erledigte_auftrage",
    "erledigte_pakete",
    "erledigte_teile",
)
REQUIRED_INDEXES = (0, 12, 13, 14, 16, 17, 18)


def _resolve_excel_file(path: str | None = None) -> Path:
    """Vrátí konkrétní Excel soubor nebo nejnovější Excel ve složce."""
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

        return max(candidates, key=lambda p: p.stat().st_mtime)

    raise FileNotFoundError(f"Excel cesta neexistuje: {source}")


def _to_numeric(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    # NaN se má chovat stejně jako pandas errors="coerce".
    return number if number == number else None


def _normalize_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None

    for parser in (
        lambda s: date.fromisoformat(s),
        lambda s: datetime.fromisoformat(s).date(),
    ):
        try:
            return parser(text)
        except ValueError:
            pass

    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def _read_openxml_rows(path: Path) -> Iterator[Sequence[object]]:
    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        worksheet = workbook.worksheets[0]
        if worksheet.max_column <= max(REQUIRED_INDEXES):
            raise ValueError(
                "Excel nemá očekávané sloupce A/M/N/O/Q/R/S "
                f"(nalezeno {worksheet.max_column} sloupců)."
            )
        # Pandas read_excel používal první řádek jako hlavičku, proto začínáme řádkem 2.
        for values in worksheet.iter_rows(
            min_row=2, max_col=max(REQUIRED_INDEXES) + 1, values_only=True
        ):
            yield values
    finally:
        workbook.close()


def _read_xls_rows(path: Path) -> Iterator[Sequence[object]]:
    import xlrd

    workbook = xlrd.open_workbook(path)
    worksheet = workbook.sheet_by_index(0)
    if worksheet.ncols <= max(REQUIRED_INDEXES):
        raise ValueError(
            "Excel nemá očekávané sloupce A/M/N/O/Q/R/S "
            f"(nalezeno {worksheet.ncols} sloupců)."
        )

    for row_idx in range(1, worksheet.nrows):
        values = [worksheet.cell_value(row_idx, col) for col in range(max(REQUIRED_INDEXES) + 1)]
        date_cell = worksheet.cell(row_idx, 0)
        if date_cell.ctype == xlrd.XL_CELL_DATE:
            values[0] = xlrd.xldate_as_datetime(date_cell.value, workbook.datemode)
        yield values


def _iter_excel_rows(path: Path) -> Iterator[Sequence[object]]:
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        yield from _read_openxml_rows(path)
        return
    if suffix == ".xls":
        yield from _read_xls_rows(path)
        return
    raise ValueError(f"Nepodporovaný Excel formát: {path.suffix}")


def read_excel_data(path: str | None = None) -> list[dict]:
    """
    Načte KPI tabulku a vrátí očištěné řádky bez závislosti na pandas.

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
    rows: list[dict] = []

    for raw in _iter_excel_rows(excel_file):
        datum = _normalize_date(raw[0])
        values = [_to_numeric(raw[index]) for index in REQUIRED_INDEXES[1:]]

        if datum is None or not any(value is not None for value in values):
            continue

        rows.append(
            {
                "datum": datum,
                **dict(zip(KPI_COLUMNS[1:], values)),
            }
        )

    # Pro stejné datum zachováme poslední neprázdný záznam stejně jako původní
    # drop_duplicates(..., keep="last"), včetně pořadí posledních výskytů.
    seen: set[date] = set()
    deduplicated_reversed: list[dict] = []
    for row in reversed(rows):
        datum = row["datum"]
        if datum in seen:
            continue
        seen.add(datum)
        deduplicated_reversed.append(row)

    return list(reversed(deduplicated_reversed))


def get_target_pocet_boxu(rows: Iterable[dict] | None) -> list[tuple[str, float]]:
    """Vrátí dvojice (datum, prognóza balíků/boxů) pro Prometheus metriky."""
    if rows is None:
        return []

    target: list[tuple[str, float]] = []
    for row in rows:
        datum = row.get("datum")
        value = row.get("prognose_pakete")
        if datum is None or value is None:
            continue
        datum_text = datum.isoformat() if hasattr(datum, "isoformat") else str(datum)
        target.append((datum_text, float(round(float(value)))))
    return target


def get_daily_kpi_rows(rows: Iterable[dict] | None) -> list[dict]:
    """Vrátí kompletní KPI řádky jako serializovatelný list slovníků."""
    if rows is None:
        return []

    output: list[dict] = []
    for row in rows:
        datum = row.get("datum")
        output.append(
            {
                "datum": datum.isoformat() if hasattr(datum, "isoformat") else str(datum),
                **{column: row.get(column) for column in KPI_COLUMNS[1:]},
            }
        )
    return output
