def make_int(value) -> int | None:
    if value is not None:
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    return None


def convert_to_serializable(value):
    """Convert given value to serializable object."""
    if isinstance(value, set):
        return list(value)
    elif isinstance(value, dict):
        return {k: convert_to_serializable(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        return [convert_to_serializable(item) for item in value]
    else:
        return value
