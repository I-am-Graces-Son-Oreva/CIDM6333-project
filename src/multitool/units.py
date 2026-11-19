_LENGTH_IN_METERS = {
    "m": 1.0,
    "km": 1000.0,
    "ft": 0.3048,
    "mi": 1609.344,
}


def _convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
    if to_unit not in {"C", "F", "K"}:
        raise ValueError(f"incompatible or unknown unit: {to_unit}")
    if from_unit == "C":
        celsius = value
    elif from_unit == "F":
        celsius = (value - 32) * 5 / 9
    else:
        celsius = value - 273.15
    if to_unit == "C":
        return celsius
    if to_unit == "F":
        return celsius * 9 / 5 + 32
    return celsius + 273.15


def convert(value: float, from_unit: str, to_unit: str) -> float:
    if from_unit in _LENGTH_IN_METERS:
        if to_unit not in _LENGTH_IN_METERS:
            raise ValueError(f"incompatible or unknown unit: {to_unit}")
        return value * _LENGTH_IN_METERS[from_unit] / _LENGTH_IN_METERS[to_unit]

    if from_unit in {"C", "F", "K"}:
        return _convert_temperature(value, from_unit, to_unit)

    raise ValueError(f"unknown unit: {from_unit}")
