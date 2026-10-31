"""Cover position mapping shared by reads and commands."""
import math


def displayed_position(raw, inverted=False):
    try:
        value = float(raw)
    except (ValueError, TypeError):
        return None
    if not math.isfinite(value) or not 0 <= value <= 100:
        return None
    result = 100 if value >= 99 else 0 if value <= 1 else round(value)
    return 100-result if inverted else result


def native_position(position, inverted=False):
    if type(position) is not int or not 0 <= position <= 100:
        raise ValueError('Cover position must be an integer between 0 and 100')
    return min(99, 100-position if inverted else position)
