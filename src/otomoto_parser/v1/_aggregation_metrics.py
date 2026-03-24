from __future__ import annotations

from typing import Any

import pandas as pd

from ._aggregation_common import HEADER


def range_str(series: pd.Series) -> str:
    values = series.dropna()
    if values.empty:
        return ""
    minimum = int(values.min())
    maximum = int(values.max())
    return str(minimum) if minimum == maximum else f"{minimum}-{maximum}"


def median_int(series: pd.Series) -> int | None:
    values = series.dropna()
    if values.empty:
        return None
    return int(round(float(values.median())))


def agg_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    registered_values = frame["registered"].dropna()
    registered_pct = float(registered_values.mean()) if not registered_values.empty else None
    return {
        "count": int(frame.shape[0]),
        "year_range": range_str(frame["year"]),
        "price_range": range_str(frame["price"]),
        "mileage_median": median_int(frame["mileage"]),
        "registered_pct": registered_pct,
    }


def build_hier_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=HEADER)

    rows: list[dict[str, Any]] = []
    for make in frame.groupby("make").size().sort_values(ascending=False).index:
        make_frame = frame[frame["make"] == make]
        make_metrics = agg_metrics(make_frame)
        rows.extend(_model_rows(make, make_frame, make_metrics))
    return pd.DataFrame(rows, columns=HEADER)


def _model_rows(make: str, make_frame: pd.DataFrame, make_metrics: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model in make_frame.groupby("model").size().sort_values(ascending=False).index:
        model_frame = make_frame[make_frame["model"] == model]
        model_metrics = agg_metrics(model_frame)
        for body_type in model_frame.groupby("body_type").size().sort_values(ascending=False).index:
            body_frame = model_frame[model_frame["body_type"] == body_type]
            rows.append(
                _build_row(
                    {"make": make, "model": model, "body_type": body_type},
                    {"make": make_metrics, "model": model_metrics, "body": agg_metrics(body_frame)},
                )
            )
    return rows


def _build_row(identity: dict[str, str], metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "make": identity["make"],
        "make_count": metrics["make"]["count"],
        "make_year_range": metrics["make"]["year_range"],
        "make_price_range": metrics["make"]["price_range"],
        "make_mileage_median": metrics["make"]["mileage_median"],
        "make_registered_pct_pl": metrics["make"]["registered_pct"],
        "model": identity["model"],
        "model_count": metrics["model"]["count"],
        "model_year_range": metrics["model"]["year_range"],
        "model_price_range": metrics["model"]["price_range"],
        "model_mileage_median": metrics["model"]["mileage_median"],
        "model_registered_pct_pl": metrics["model"]["registered_pct"],
        "body_type": identity["body_type"],
        "body_count": metrics["body"]["count"],
        "body_year_range": metrics["body"]["year_range"],
        "body_price_range": metrics["body"]["price_range"],
        "body_mileage_median": metrics["body"]["mileage_median"],
        "body_registered_pct_pl": metrics["body"]["registered_pct"],
    }
