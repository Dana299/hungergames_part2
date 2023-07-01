def make_int(value) -> int | None:
    if value is not None:
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    return None