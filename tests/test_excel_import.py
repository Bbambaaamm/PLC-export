import tempfile
import unittest
from datetime import date
from pathlib import Path

from openpyxl import Workbook

from dataExcelImport.dataImport import (
    get_daily_kpi_rows,
    get_target_pocet_boxu,
    read_excel_data,
)


class ExcelImportTests(unittest.TestCase):
    def _make_workbook(self, path: Path) -> None:
        wb = Workbook()
        ws = wb.active
        ws.append([f"col{i}" for i in range(1, 20)])

        def row(day, target=None, actual=None):
            values = [None] * 19
            values[0] = day
            values[12] = 1
            values[13] = target
            values[14] = 3
            values[16] = 4
            values[17] = actual
            values[18] = 6
            return values

        ws.append(row(date(2026, 10, 4), 100.4, 90))
        ws.append(row(date(2026, 10, 5), 200.6, 180))
        ws.append(row(date(2026, 10, 5), 250.2, 220))  # poslední duplikát vyhrává
        ws.append([None] * 19)
        wb.save(path)

    def test_xlsx_import_without_pandas(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.xlsx"
            self._make_workbook(path)
            rows = read_excel_data(str(path))

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["datum"], date(2026, 10, 4))
        self.assertEqual(rows[1]["datum"], date(2026, 10, 5))
        self.assertEqual(rows[1]["prognose_pakete"], 250.2)
        self.assertEqual(
            get_target_pocet_boxu(rows),
            [("2026-10-04", 100.0), ("2026-10-05", 250.0)],
        )
        serializable = get_daily_kpi_rows(rows)
        self.assertEqual(serializable[1]["datum"], "2026-10-05")


if __name__ == "__main__":
    unittest.main()
