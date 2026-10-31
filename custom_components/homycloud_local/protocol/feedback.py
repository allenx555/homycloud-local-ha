"""Command feedback rules: no optimistic state, no automatic retries."""
import math


def same_value(actual, expected):
    if type(expected) is bool:
        return actual == ('true' if expected else 'false')
    if type(expected) in (int, float):
        try:
            value = float(actual)
            return math.isfinite(value) and abs(value-expected) < 1e-6
        except (ValueError, TypeError):
            return False
    return actual == expected


def confirmed(samples, key, expected, issued_at, baseline):
    current = samples.get(key)
    if current and current.received_monotonic >= issued_at:
        if same_value(current.value, expected):
            return True
        if key == 'percent_control':
            previous = baseline.get(key)
            if previous:
                try:
                    start, now, target = float(previous.value), float(current.value), float(expected)
                    if min(start, target) <= now <= max(start, target) and now != start:
                        return True
                except (ValueError, TypeError):
                    pass
    # Long curtain travel must not time out simply because it has not reached the endpoint.
    if key == 'percent_control':
        motion = samples.get('control')
        previous = baseline.get('control')
        if motion and motion.received_monotonic >= issued_at and motion.value in ('open','close','continue'):
            if motion.timestamp is not None and (previous is None or previous.timestamp is None or motion.timestamp > previous.timestamp):
                return True
    return False
