from __future__ import annotations

from typing import Any


HEADER = [
    "make",
    "make_count",
    "make_year_range",
    "make_price_range",
    "make_mileage_median",
    "make_registered_pct_pl",
    "model",
    "model_count",
    "model_year_range",
    "model_price_range",
    "model_mileage_median",
    "model_registered_pct_pl",
    "body_type",
    "body_count",
    "body_year_range",
    "body_price_range",
    "body_mileage_median",
    "body_registered_pct_pl",
]


class AggregationError(RuntimeError):
    pass


def safe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int | float):
            return int(value)
        text = str(value).strip()
        if not text:
            return None
        return int(float(text))
    except Exception:
        return None
