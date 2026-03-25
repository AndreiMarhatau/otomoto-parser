from __future__ import annotations

from typing import Any

from ._service_analysis_payload_common import _compact_dict
from ._service_analysis_payload_support import _IDENTIFIER_PARAMETER_ALIASES, _LISTING_PARAMETER_FIELDS, _MAX_DESCRIPTION_LENGTH, _MAX_SHORT_DESCRIPTION_LENGTH
from ._service_analysis_report_payload import build_vehicle_report_payload as _build_vehicle_report_payload
from ._service_listing_helpers import _location_display, _param_display, _param_map, _price_evaluation_display, _price_fields


def build_listing_payload(listing: dict[str, Any], record: dict[str, Any], listing_page: dict[str, Any] | None) -> dict[str, Any]:
    node = record.get("node") if isinstance(record.get("node"), dict) else {}
    detail_parameters = listing_page.get("parameters") if isinstance(listing_page, dict) else None
    merged_parameters = _selected_parameter_payload(node.get("parameters"))
    merged_parameters.update(_selected_parameter_payload(detail_parameters))
    merged_parameters.update(_selected_detail_parameter_payload((listing_page or {}).get("parametersDict")))
    return _compact_dict(
        {
            "title": listing.get("title") or node.get("title") or (listing_page or {}).get("title"),
            "url": listing.get("url"),
            "location": listing.get("location") or _location_display(node.get("location")) or _location_display((listing_page or {}).get("location")),
            "createdAt": node.get("createdAt") or (listing_page or {}).get("createdAt"),
            "price": _listing_price_payload(node),
            "seller": _seller_payload(node.get("sellerLink")) or _seller_payload((listing_page or {}).get("sellerLink")),
            "listingContent": _compact_dict(
                {
                    "dataVerified": node.get("cepikVerified"),
                    "badges": _listing_badges(node.get("valueAddedServices")),
                    "shortDescription": _truncate_text(node.get("shortDescription"), _MAX_SHORT_DESCRIPTION_LENGTH),
                    "description": _truncate_text((listing_page or {}).get("description"), _MAX_DESCRIPTION_LENGTH),
                }
            ),
            "vehicle": _compact_dict({"identifiers": _identifier_payload(listing, node.get("parameters"), detail_parameters), **merged_parameters}),
        }
    )


def build_vehicle_report_payload(report_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    return _build_vehicle_report_payload(report_payload)


def _truncate_text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    if not normalized:
        return None
    return normalized if len(normalized) <= limit else normalized[:limit] if limit <= 3 else f"{normalized[: limit - 3].rstrip()}..."


def _selected_parameter_payload(parameters: list[dict[str, Any]] | None) -> dict[str, Any]:
    parameter_map = _param_map(parameters)
    selected: dict[str, Any] = {}
    for source_key, target_key in _LISTING_PARAMETER_FIELDS:
        value = _param_display(parameter_map, source_key)
        if value not in (None, ""):
            selected[target_key] = value
    return _compact_dict(selected)


def _selected_detail_parameter_payload(parameters_dict: Any) -> dict[str, Any]:
    if not isinstance(parameters_dict, dict):
        return {}
    selected: dict[str, Any] = {}
    for source_key, target_key in _LISTING_PARAMETER_FIELDS:
        value = _parameter_value_from_detail_entry(parameters_dict.get(source_key))
        if value not in (None, ""):
            selected[target_key] = value
    return _compact_dict(selected)


def _parameter_value_from_detail_entry(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return None
    direct_value = entry.get("displayValue") or entry.get("label")
    if direct_value not in (None, ""):
        return str(direct_value)
    values = entry.get("values")
    if isinstance(values, list):
        for item in values:
            if isinstance(item, dict):
                candidate = item.get("label") or item.get("displayValue")
                if candidate not in (None, ""):
                    return str(candidate)
    raw_value = entry.get("value")
    if raw_value not in (None, ""):
        return str(raw_value)
    if isinstance(values, list):
        for item in values:
            if isinstance(item, dict) and item.get("value") not in (None, ""):
                return str(item["value"])
    return None


def _identifier_payload(listing: dict[str, Any], search_parameters: list[dict[str, Any]] | None, detail_parameters: list[dict[str, Any]] | None) -> dict[str, Any]:
    search_parameter_map = _param_map(search_parameters)
    detail_parameter_map = _param_map(detail_parameters)
    identifiers: dict[str, Any] = {}
    for source_key, target_key in _IDENTIFIER_PARAMETER_ALIASES.items():
        value = listing.get(target_key) or _param_display(search_parameter_map, source_key) or _param_display(detail_parameter_map, source_key)
        if value not in (None, ""):
            identifiers[target_key] = value
    return identifiers


def _listing_price_payload(node: dict[str, Any]) -> dict[str, Any]:
    amount, currency = _price_fields(node)
    return _compact_dict({"amount": amount, "currency": currency, "marketPriceAssessment": _price_evaluation_display(node.get("priceEvaluation"))})


def _seller_payload(raw_seller: Any) -> dict[str, Any] | None:
    if isinstance(raw_seller, str) and raw_seller:
        return {"websiteUrl": raw_seller}
    if not isinstance(raw_seller, dict):
        return None
    return _compact_dict({key: raw_seller.get(key) for key in ("name", "websiteUrl", "isCreditIntermediary")})


def _listing_badges(raw_badges: Any) -> list[str]:
    if not isinstance(raw_badges, list):
        return []
    return [str(item.get("name")).strip() for item in raw_badges if isinstance(item, dict) and str(item.get("name") or "").strip()]
