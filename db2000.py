"""DB2000 contract from dataBlockActin.pdf (TIA export dated 2024-05-02).

Offsets are bytes; bit positions are explicit. No writes or inferred topology.
"""

BR_POSITIONS = {
    "BR01": {"box": 68, "code": 192, "direction": 194, "weight": 80},
    "BR02": {"box": 1220, "code": 1334},
    "BR06": {"box": 2360, "code": 2506, "direction": 2508, "shipping": 2372},
    "BR08": {"box": 3534, "code": 3648, "direction": 3650},
    "BR09": {"box": 4676, "code": 4790, "direction": 4792},
    "BR10": {"box": 5818, "code": 5932, "direction": 5934},
    "BR11": {"box": 6960, "code": 7074, "direction": 7076},
}

ESTOPS = [
    ("ESTOP5", 64, 0, "Hlavní rozvaděč"),
    ("ESTOP4", 64, 1, "Za Ranpak V10"),
    ("ESTOP8", 64, 2, "Za Plausicheckem před vraty 38"),
    ("ESTOP9", 64, 3, "Konec dopravníku před vraty 41"),
    ("ESTOP6_7", 64, 4, "Klec AKL – společný signál obou stran"),
    ("ESTOP2", 64, 5, "Podružný rozvaděč =RP"),
    ("ESTOP1", 64, 6, "Začátek dopravníku Smartlog"),
    ("ESTOP3", 64, 7, "U váhy"),
    ("ESTOP_teleskop_T1", 65, 0, "Levý teleskop T1"),
    ("ESTOP_teleskop_T2", 65, 1, "Pravý teleskop T2"),
]

WAITING = {
    "vaha": "prostoj1", "V10": "prostoj2", "V20": "prostoj3",
    "AKL1": "prostoj4", "AKL2": "prostoj5", "T2": "prostoj6", "T1": "prostoj7",
}
MATERIALS = {
    ("V10", "vika"): ("V10_bLidSupplyLow", "V10_bLidSupplyLowError"),
    ("V10", "lepidlo"): (None, "V10_bGlueSupplyLowError"),
    ("V20", "vika"): ("V20_bLidSupplyLow", "V20_bLidSupplyLowError"),
    ("V20", "lepidlo"): (None, "V20_bGlueSupplyLowError"),
    ("AKL1", "etikety"): ("Line1_LabelWarning", "Line1_LabelOut"),
    ("AKL1", "paska"): ("Line1_RibbonWarning", "Line1_RibbonOut"),
    ("AKL2", "etikety"): ("Line2_LabelWarning", "Line2_LabelOut"),
    ("AKL2", "paska"): ("Line2_RibbonWarning", "Line2_RibbonOut"),
}


def s7_string(data, offset, capacity):
    """Decode only the declared payload; never accept trailing buffer content."""
    if offset < 0 or len(data) < offset + capacity + 2:
        raise ValueError("Truncated S7 STRING")
    maximum, length = data[offset:offset + 2]
    if maximum != capacity or length > maximum:
        raise ValueError("Invalid S7 STRING header")
    value = bytes(data[offset + 2:offset + 2 + length]).decode("ascii")
    if any(ord(c) < 32 or ord(c) > 126 for c in value):
        raise ValueError("Non-printable characters in S7 STRING")
    return value.strip()


def decode_position(data, name):
    spec = BR_POSITIONS[name]
    if len(data) < spec["code"] + 2:
        raise ValueError("Truncated BR response")
    result = {
        "box_id": s7_string(data, spec["box"], 10),
        "code": int.from_bytes(data[spec["code"]:spec["code"] + 2], "big", signed=True),
        "direction": None,
    }
    if "direction" in spec:
        if len(data) <= spec["direction"]:
            raise ValueError("Truncated BR direction")
        result["direction"] = int.from_bytes(data[spec["direction"]:spec["direction"] + 1], "big", signed=True)
    if "shipping" in spec:
        result["shipping_label"] = s7_string(data, spec["shipping"], 30)
    if "weight" in spec:
        # Unit/decimal convention is not documented; keep original text.
        result["weight_text"] = s7_string(data, spec["weight"], 7)
    return result


def response_group(code):
    return "ok" if code == 200 else "error" if 400 <= code <= 499 else "idle" if code == 0 else "other"
