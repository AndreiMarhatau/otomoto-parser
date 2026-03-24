from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from ._service_common import (
    CATEGORY_DATA_NOT_VERIFIED,
    CATEGORY_IMPORTED_FROM_US,
    CATEGORY_PRICE_OUT_OF_RANGE,
    CATEGORY_TO_BE_CHECKED,
    DEFAULT_REPORT_LOOKUP_DAYS_BACK,
    DEFAULT_REPORT_LOOKUP_DAYS_FORWARD,
    STRICT_DATE_RE,
    utc_now,
)


def _date_range_defaults() -> tuple[str, str]:
    today = datetime.now(UTC).date()
    return ((today - timedelta(days=DEFAULT_REPORT_LOOKUP_DAYS_BACK)).isoformat(), (today + timedelta(days=DEFAULT_REPORT_LOOKUP_DAYS_FORWARD)).isoformat())


def _normalize_lookup_date(value: str) -> str:
    if not isinstance(value, str) or not STRICT_DATE_RE.fullmatch(value):
        raise RuntimeError("Invalid date format. Use YYYY-MM-DD.")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise RuntimeError("Invalid date format. Use YYYY-MM-DD.") from exc


def _normalize_lookup_identifier(value: str, *, label: str) -> str:
    normalized = "".join(str(value).upper().split())
    if not normalized:
        raise RuntimeError(f"{label} cannot be empty.")
    return normalized


def _report_lookup_options(details: dict[str, Any]) -> dict[str, Any]:
    default_from, default_to = _date_range_defaults()
    return {
        "reason": details["reason"],
        "vin": details.get("vin"),
        "registrationNumber": details.get("registration_number"),
        "firstRegistrationDate": details.get("first_registration_date"),
        "dateRange": {"from": details.get("date_from") or details.get("first_registration_date") or default_from, "to": details.get("date_to") or default_to},
        "error": details.get("error"),
    }


def _param_map(parameters: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for param in parameters or []:
        key = param.get("key") or param.get("name")
        if isinstance(key, str) and key:
            result[key] = param
    return result


def _param_display(parameters: dict[str, dict[str, Any]], key: str) -> str | None:
    value = (parameters.get(key) or {}).get("displayValue") or (parameters.get(key) or {}).get("value")
    return str(value) if value not in (None, "") else None


def _location_display(location: Any) -> str | None:
    if not isinstance(location, dict):
        return None
    city_name = _location_name(location.get("city"))
    region_name = _location_name(location.get("region"))
    return f"{city_name}, {region_name}" if city_name and region_name else city_name or region_name


def _location_name(part: Any) -> str | None:
    if isinstance(part, str) and part:
        return part
    if isinstance(part, dict) and isinstance(part.get("name"), str) and part["name"]:
        return part["name"]
    return None


def _price_fields(node: dict[str, Any]) -> tuple[int | str | None, str]:
    price = node.get("price") if isinstance(node.get("price"), dict) else {}
    amount = price.get("amount") if isinstance(price.get("amount"), dict) else {}
    value = amount.get("units") or price.get("value")
    return value, amount.get("currencyCode") or price.get("currency") or "PLN"


def _price_evaluation_display(price_evaluation: Any) -> str | None:
    if not isinstance(price_evaluation, dict):
        return None
    for key in ("indicator", "rating"):
        value = price_evaluation.get(key)
        if isinstance(value, str) and value and value.upper() != "NONE":
            return value
    return None


def _is_out_of_range_price_evaluation(price_evaluation: Any) -> bool:
    if not isinstance(price_evaluation, dict) or not price_evaluation:
        return True
    seen_value = False
    for key in ("indicator", "rating"):
        value = price_evaluation.get(key)
        if isinstance(value, str) and value:
            seen_value = True
            if value.upper() != "NONE":
                return False
    return seen_value


def _is_us_origin(country_origin: Any) -> bool:
    return isinstance(country_origin, str) and country_origin.strip().lower() in {"us", "usa", "united-states", "united_states"}


def summarize_record(record: dict[str, Any]) -> dict[str, Any]:
    node = record.get("node") if isinstance(record.get("node"), dict) else {}
    parameters = _param_map(node.get("parameters"))
    country_origin = parameters.get("country_origin", {}).get("value")
    price_evaluation = node.get("priceEvaluation")
    return {
        "id": record.get("item_id") or record.get("item_key"),
        "category": _record_category(price_evaluation, country_origin, node.get("cepikVerified")),
        "title": node.get("title"),
        "shortDescription": node.get("shortDescription"),
        "url": node.get("url"),
        "imageUrl": ((node.get("thumbnail") or {}).get("x2")) or ((node.get("thumbnail") or {}).get("x1")),
        "price": _price_fields(node)[0],
        "priceCurrency": _price_fields(node)[1],
        "priceEvaluation": _price_evaluation_display(price_evaluation),
        "dataVerified": bool(node.get("cepikVerified")) if isinstance(node.get("cepikVerified"), bool) else None,
        "engineCapacity": _param_display(parameters, "engine_capacity"),
        "enginePower": _param_display(parameters, "engine_power"),
        "year": _param_display(parameters, "year"),
        "mileage": _param_display(parameters, "mileage"),
        "fuelType": _param_display(parameters, "fuel_type"),
        "transmission": _param_display(parameters, "gearbox"),
        "location": _location_display(node.get("location")),
        "createdAt": node.get("createdAt"),
        "countryOrigin": parameters.get("country_origin", {}).get("displayValue") or country_origin,
    }


def _record_category(price_evaluation: Any, country_origin: Any, data_verified: Any) -> str:
    if _is_out_of_range_price_evaluation(price_evaluation):
        return CATEGORY_PRICE_OUT_OF_RANGE
    if _is_us_origin(country_origin):
        return CATEGORY_IMPORTED_FROM_US
    if data_verified is False:
        return CATEGORY_DATA_NOT_VERIFIED
    return CATEGORY_TO_BE_CHECKED


def build_categorized_payload(results_path: Path) -> dict[str, Any]:
    listings = [summarize_record(json.loads(line)) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    categories = {name: [] for name in [CATEGORY_PRICE_OUT_OF_RANGE, CATEGORY_IMPORTED_FROM_US, CATEGORY_DATA_NOT_VERIFIED, CATEGORY_TO_BE_CHECKED]}
    for listing in listings:
        categories[listing["category"]].append(listing)
    return {
        "generatedAt": utc_now(),
        "totalCount": len(listings),
        "categories": {name: {"label": name, "count": len(items), "items": items} for name, items in categories.items()},
    }
