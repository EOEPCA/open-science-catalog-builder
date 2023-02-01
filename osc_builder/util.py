from datetime import date
from typing import Any, Optional


def parse_decimal_date(source: Optional[str]) -> Optional[date]:
    if not source:
        return None
    dot_count = source.count(".")
    if not dot_count:
        return date(int(source), 1, 1)
    if dot_count == 1:
        year, month = source.split(".")
        return date(int(year), int(month) + 1, 1)
    elif dot_count == 2:
        year, month, day = source.split(".")
        return date(int(year), int(month), int(day))
    return None


def get_depth(maybe_list: Any) -> int:
    if isinstance(maybe_list, (list, tuple)):
        return get_depth(maybe_list[0]) + 1
    return 0
