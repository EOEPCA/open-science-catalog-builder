from datetime import date
from typing import Any


def parse_decimal_date(source):
    if not source:
        return None
    year, month = source.split(".")
    return date(int(year), int(month) + 1, 1)


def get_depth(maybe_list: Any) -> int:
    if isinstance(maybe_list, (list, tuple)):
        return get_depth(maybe_list[0]) + 1
    return 0
