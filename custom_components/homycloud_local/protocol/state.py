"""State ordering and command validation, independent of DDS and Home Assistant."""
from dataclasses import dataclass
import math
import time


@dataclass(frozen=True)
class Sample:
    value: str
    timestamp: int | None
    received_at: float
    received_monotonic: float = 0


class StateStore:
    def __init__(self):
        self.values: dict[str, dict[str, Sample]] = {}
        self.last_seen: dict[str, float] = {}

    def update(self, device_id: str, key: str, value: str, timestamp=None) -> bool:
        try:
            stamp = int(timestamp) if timestamp is not None else None
        except (ValueError, TypeError):
            stamp = None
        previous = self.values.get(device_id, {}).get(key)
        self.last_seen[device_id] = time.monotonic()
        if previous and previous.timestamp is not None:
            if stamp is None or stamp < previous.timestamp:
                return False
            if stamp == previous.timestamp and str(value) != previous.value:
                return False
        self.values.setdefault(device_id, {})[key] = Sample(str(value), stamp, time.time(), time.monotonic())
        return previous is None or previous.value != str(value)

    def snapshot(self) -> dict:
        return {did: {key: sample.value for key, sample in attrs.items()}
                for did, attrs in self.values.items()}


def validate_command(device: dict, key: str, value):
    """Accept only capabilities explicitly represented in the inventory."""
    entity = device.get('entities', {}).get(key, {})
    component = entity.get('component')
    if component == 'switch' and type(value) is bool:
        return value
    if device.get('kind') == 'cover':
        if key == 'control' and value == 'stop':
            return value
        if key == 'percent_control' and type(value) is int and 0 <= value <= 99:
            return value
    if component == 'number' and type(value) in (int, float) and math.isfinite(value):
        limits = entity['extra']
        step = limits.get('step', 1)
        if limits['min'] <= value <= limits['max'] and abs((value-limits['min']) / step - round((value-limits['min']) / step)) < 1e-6:
            return float(value)
    if component == 'select' and value in entity['extra']['options']:
        return entity.get('command_values', {}).get(value, value)
    caps = device.get('hvac', {})
    if key == 'temp_set' and caps.get('temperature') and type(value) in (int, float):
        if math.isfinite(value) and 16 <= value <= 30 and float(value).is_integer():
            return float(value)
    if key == 'level' and caps.get('fan') and value in ('auto', 'low', 'middle', 'high'):
        return value
    if key == 'mode' and caps.get('mode') and value in caps.get('modes', {}).values() and value is not None:
        return value
    raise ValueError(f'Unsupported or invalid command: {key}')
