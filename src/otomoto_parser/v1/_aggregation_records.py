from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from ._aggregation_common import HEADER, safe_int


def get_param(params: list[dict[str, Any]] | None, key: str) -> str | None:
    for param in params or []:
        if param.get("key") == key:
            return param.get("value") or param.get("displayValue")
    return None


def parse_listing(obj: dict[str, Any]) -> dict[str, Any]:
    node = obj.get("node") or (obj.get("edge") or {}).get("node") or {}
    params = node.get("parameters") or []

    registered_raw = get_param(params, "registered")
    registered = _normalize_registered_value(registered_raw)
    price = safe_int(((node.get("price") or {}).get("amount") or {}).get("units"))
    return {
        "make": get_param(params, "make"),
        "model": get_param(params, "model"),
        "body_type": get_param(params, "body_type"),
        "year": safe_int(get_param(params, "year")),
        "price": price,
        "mileage": safe_int(get_param(params, "mileage")),
        "registered": registered,
    }


def _normalize_registered_value(value: str | None) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return 1 if str(value).strip().lower() in {"1", "true", "tak", "yes"} else 0


def read_jsonl(path: Path) -> pd.DataFrame:
    rows = [_parse_row(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [row for row in rows if row is not None]
    if not rows:
        return pd.DataFrame(columns=_record_columns())

    frame = pd.DataFrame(rows).dropna(subset=["make", "model", "body_type"], how="any")
    for column in ["year", "price", "mileage", "registered"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "registered" not in frame.columns:
        frame["registered"] = pd.Series(dtype="float64")
    return frame


def _parse_row(line: str) -> dict[str, Any] | None:
    return parse_listing(json.loads(line))


def _record_columns() -> list[str]:
    return [HEADER[index] for index in (0, 6, 12)] + ["year", "price", "mileage", "registered"]
