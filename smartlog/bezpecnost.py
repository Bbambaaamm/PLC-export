"""Smartlog ESTOP: identifiers match DB2000; ESTOP6_7 is one shared input."""
from db2000 import ESTOPS


def read_bezpecnost_smartlog(data, last_data) -> None:
    if len(data) < 66:
        return
    last_data["smartlog_estops"] = {
        name: int(bool(data[byte] & (1 << bit)))
        for name, byte, bit, location in ESTOPS
    }
