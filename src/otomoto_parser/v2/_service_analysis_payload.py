from __future__ import annotations

from typing import Any

from ._service_listing_helpers import _location_display, _param_display, _param_map, _price_evaluation_display, _price_fields

_LISTING_PARAMETER_KEYS = ("make", "model", "version", "generation", "year", "mileage", "fuel_type", "gearbox", "body_type", "engine_capacity", "engine_power", "drive", "doors_no", "seats_no", "color", "registered", "country_origin", "condition", "origin_country")
_IDENTIFIER_PARAMETER_ALIASES = {"vin": "vin", "registration": "registrationNumber", "date_registration": "firstRegistrationDate"}
_MAX_SHORT_DESCRIPTION_LENGTH = 600
_MAX_DESCRIPTION_LENGTH = 3000
_MAX_TIMELINE_EVENTS = 8
_MAX_TIMELINE_EVENT_FIELDS = ("date", "type", "label", "mileage", "country", "source")

def build_listing_payload(listing: dict[str, Any], record: dict[str, Any], listing_page: dict[str, Any] | None) -> dict[str, Any]:
    node = record.get("node") if isinstance(record.get("node"), dict) else {}
    detail_parameters = listing_page.get("parameters") if isinstance(listing_page, dict) else None
    search_parameters = node.get("parameters")
    merged_parameters = _selected_parameter_payload(search_parameters)
    merged_parameters.update(_selected_parameter_payload(detail_parameters))
    merged_parameters.update(_selected_detail_parameter_payload((listing_page or {}).get("parametersDict")))
    return _compact_dict(
        {
            "id": listing.get("id"),
            "url": listing.get("url"),
            "title": listing.get("title") or node.get("title") or (listing_page or {}).get("title"),
            "location": listing.get("location") or _location_display(node.get("location")) or _location_display((listing_page or {}).get("location")),
            "createdAt": node.get("createdAt") or (listing_page or {}).get("createdAt"),
            "price": _listing_price_payload(node),
            "seller": _seller_payload(node.get("sellerLink")) or _seller_payload((listing_page or {}).get("sellerLink")),
            "dataVerified": node.get("cepikVerified"),
            "shortDescription": _truncate_text(node.get("shortDescription"), _MAX_SHORT_DESCRIPTION_LENGTH),
            "description": _truncate_text((listing_page or {}).get("description"), _MAX_DESCRIPTION_LENGTH),
            "identifiers": _identifier_payload(listing, search_parameters, detail_parameters),
            "parameters": merged_parameters,
            "badges": _listing_badges(node.get("valueAddedServices")),
        }
    )

def build_vehicle_report_payload(report_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(report_payload, dict):
        return None
    report = report_payload.get("report") if isinstance(report_payload.get("report"), dict) else {}
    technical_data_root = _technical_data_root(report)
    basic_data = technical_data_root.get("basicData") if isinstance(technical_data_root.get("basicData"), dict) else {}
    ownership_history = technical_data_root.get("ownershipHistory") if isinstance(technical_data_root.get("ownershipHistory"), dict) else {}
    return _compact_dict(
        {
            "identity": report_payload.get("identity"),
            "summary": report_payload.get("summary"),
            "sourceStatus": _source_status_payload(report_payload, report),
            "technicalData": _technical_summary_payload(basic_data, ownership_history),
            "timeline": _timeline_payload(report.get("timeline_data")),
            "autodnaSummary": report.get("autodna_data", {}).get("summary") if isinstance(report.get("autodna_data"), dict) else None,
            "carfaxSummary": report.get("carfax_data", {}).get("summary") if isinstance(report.get("carfax_data"), dict) else None,
        }
    )

def _compact_dict(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item not in (None, "", [], {})}

def _truncate_text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    if not normalized:
        return None
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] if limit <= 3 else f"{normalized[: limit - 3].rstrip()}..."

def _selected_parameter_payload(parameters: list[dict[str, Any]] | None) -> dict[str, Any]:
    parameter_map = _param_map(parameters)
    return _compact_dict({key: _param_display(parameter_map, key) for key in _LISTING_PARAMETER_KEYS})

def _selected_detail_parameter_payload(parameters_dict: Any) -> dict[str, Any]:
    if not isinstance(parameters_dict, dict):
        return {}
    return _compact_dict({key: _parameter_value_from_detail_entry(parameters_dict.get(key)) for key in _LISTING_PARAMETER_KEYS})

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

def _identifier_payload(
    listing: dict[str, Any],
    search_parameters: list[dict[str, Any]] | None,
    detail_parameters: list[dict[str, Any]] | None,
) -> dict[str, Any]:
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
    return _compact_dict({"amount": amount, "currency": currency, "evaluation": _price_evaluation_display(node.get("priceEvaluation"))})

def _seller_payload(raw_seller: Any) -> dict[str, Any] | str | None:
    if isinstance(raw_seller, str) and raw_seller:
        return raw_seller
    if not isinstance(raw_seller, dict):
        return None
    return _compact_dict({key: raw_seller.get(key) for key in ("id", "name", "websiteUrl", "isCreditIntermediary")})

def _listing_badges(raw_badges: Any) -> list[str]:
    if not isinstance(raw_badges, list):
        return []
    return [str(item.get("name")).strip() for item in raw_badges if isinstance(item, dict) and str(item.get("name") or "").strip()]

def _timeline_payload(timeline_data: Any) -> dict[str, Any] | None:
    if not isinstance(timeline_data, dict):
        return None
    timeline_root = timeline_data.get("timelineData")
    events = timeline_root.get("events") if isinstance(timeline_root, dict) else None
    if not isinstance(events, list):
        return None
    compact_events = []
    event_types: list[str] = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if isinstance(event_type, str) and event_type and event_type not in event_types:
            event_types.append(event_type)
        if index < _MAX_TIMELINE_EVENTS:
            compact_event = _compact_dict({field: event.get(field) for field in _MAX_TIMELINE_EVENT_FIELDS})
            if compact_event:
                compact_events.append(compact_event)
    return _compact_dict({"eventCount": len(events), "eventTypes": event_types, "events": compact_events})

def _technical_data_root(report: dict[str, Any]) -> dict[str, Any]:
    technical_data = report.get("technical_data")
    if not isinstance(technical_data, dict):
        return {}
    return technical_data.get("technicalData") if isinstance(technical_data.get("technicalData"), dict) else {}

def _source_status_payload(report_payload: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    summary = report_payload.get("summary") if isinstance(report_payload.get("summary"), dict) else {}
    return _compact_dict(
        {
            "apiVersion": report.get("api_version"),
            "autodnaAvailable": summary.get("autodnaAvailable"),
            "carfaxAvailable": summary.get("carfaxAvailable"),
            "autodnaUnavailable": summary.get("autodnaUnavailable"),
            "carfaxUnavailable": summary.get("carfaxUnavailable"),
        }
    )

def _technical_summary_payload(basic_data: dict[str, Any], ownership_history: dict[str, Any]) -> dict[str, Any]:
    return _compact_dict(
        {
            "basicData": _compact_dict({"make": basic_data.get("make"), "model": basic_data.get("model"), "type": basic_data.get("type"), "modelYear": basic_data.get("modelYear"), "fuel": basic_data.get("fuel"), "engineCapacity": basic_data.get("engineCapacity"), "enginePower": basic_data.get("enginePower"), "bodyType": basic_data.get("bodyType"), "color": basic_data.get("color")}),
            "ownershipHistory": _compact_dict({"numberOfOwners": ownership_history.get("numberOfOwners"), "numberOfCoowners": ownership_history.get("numberOfCoowners"), "dateOfLastOwnershipChange": ownership_history.get("dateOfLastOwnershipChange")}),
        }
    )
