from __future__ import annotations

from typing import Any

from ._service_analysis_payload_common import _compact_dict
from ._service_analysis_report_normalization import _history_events_payload, _important_findings_payload, _report_summaries_payload
from ._service_analysis_payload_support import (
    _MAX_TIMELINE_EVENTS,
    _MAX_TIMELINE_EVENT_FIELDS,
    _NORMALIZED_REPORT_WRAPPER_KEYS,
    _REPORT_IDENTIFIER_FIELDS,
    _flatten_wrapper_values,
    _merge_wrapper_evidence,
    _source_status_payload,
    _should_skip_report_field,
    _technical_data_root,
    _technical_summary_payload,
)
from ._service_analysis_report_utils import _is_meaningful_text, _is_scalar_fact_value, _normalize_key, _scalar_or_none


def build_vehicle_report_payload(report_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(report_payload, dict):
        return None
    report = report_payload.get("report") if isinstance(report_payload.get("report"), dict) else {}
    technical_data_root = _technical_data_root(report)
    basic_data = technical_data_root.get("basicData") if isinstance(technical_data_root.get("basicData"), dict) else {}
    ownership_history = technical_data_root.get("ownershipHistory") if isinstance(technical_data_root.get("ownershipHistory"), dict) else {}
    history_events = _history_events_payload(report)
    return _compact_dict(
        {
            "identity": report_payload.get("identity"),
            "trustedIdentifiers": _trusted_identifiers_payload(report_payload, report),
            "summary": report_payload.get("summary"),
            "sourceStatus": _source_status_payload(report_payload, report, _compact_dict),
            "technicalData": _technical_summary_payload(basic_data, ownership_history, _compact_dict),
            "historyEvents": history_events,
            "timeline": _timeline_payload(report.get("timeline_data"), history_events),
            "autodnaSummary": _provider_summary_payload(report.get("autodna_data")),
            "carfaxSummary": _provider_summary_payload(report.get("carfax_data")),
            "reportSummaries": _report_summaries_payload(report),
            "importantFindings": _important_findings_payload(report),
        }
    )


def _timeline_payload(timeline_data: Any, history_events: Any) -> dict[str, Any] | None:
    raw_events = _raw_timeline_events(timeline_data)
    normalized_events = [event for event in history_events if isinstance(event, dict)] if isinstance(history_events, list) else []
    if not raw_events and not normalized_events:
        return None
    if raw_events:
        return _raw_timeline_payload(raw_events)
    return _normalized_timeline_payload(normalized_events)


def _raw_timeline_events(timeline_data: Any) -> list[dict[str, Any]]:
    if not isinstance(timeline_data, dict):
        return []
    timeline_root = timeline_data.get("timelineData")
    events = timeline_root.get("events") if isinstance(timeline_root, dict) else None
    return [event for event in events if isinstance(event, dict)] if isinstance(events, list) else []


def _raw_timeline_payload(raw_events: list[dict[str, Any]]) -> dict[str, Any]:
    return _compact_dict(
        {
            "eventCount": len(raw_events),
            "eventTypes": _timeline_event_types(raw_events),
            "events": _compact_timeline_events(raw_events[:_MAX_TIMELINE_EVENTS]),
        }
    )


def _normalized_timeline_payload(normalized_events: list[dict[str, Any]]) -> dict[str, Any]:
    return _compact_dict(
        {
            "eventCount": len(normalized_events),
            "eventTypes": _timeline_event_types(normalized_events),
            "events": _compact_timeline_events(normalized_events[:_MAX_TIMELINE_EVENTS]),
        }
    )


def _timeline_event_types(events: list[dict[str, Any]]) -> list[str]:
    event_types: list[str] = []
    for event in events:
        event_type = event.get("type")
        if isinstance(event_type, str) and event_type and event_type not in event_types:
            event_types.append(event_type)
    return event_types


def _compact_timeline_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact_events = []
    for event in events:
        compact_event = _compact_dict({field: event.get(field) for field in _MAX_TIMELINE_EVENT_FIELDS})
        if compact_event:
            compact_events.append(compact_event)
    return compact_events


def _trusted_identifiers_payload(report_payload: dict[str, Any], report: dict[str, Any]) -> dict[str, Any] | None:
    payload_identity = report_payload.get("identity") if isinstance(report_payload.get("identity"), dict) else {}
    trusted: dict[str, Any] = {}
    for source_key, target_key in (
        ("vin", "vin"),
        ("registrationNumber", "registrationNumber"),
        ("firstRegistrationDate", "firstRegistrationDate"),
        ("advertId", "advertId"),
    ):
        value = payload_identity.get(source_key)
        if value not in (None, ""):
            trusted[target_key] = value
    for source_key in _REPORT_IDENTIFIER_FIELDS:
        value = report.get(source_key)
        if value in (None, ""):
            continue
        trusted[{
            "vin_number": "vin",
            "registration_number": "registrationNumber",
            "first_registration_date": "firstRegistrationDate",
            "api_version": "apiVersion",
        }[source_key]] = value
    return _compact_dict(trusted) or None


def _provider_summary_payload(provider_data: Any) -> Any:
    if not isinstance(provider_data, dict):
        return None
    return _sanitize_summary_value(provider_data.get("summary"))


def _sanitize_summary_value(value: Any, *, path: tuple[str, ...] = ()) -> Any:
    if _is_scalar_fact_value(value):
        return _sanitize_summary_scalar(value, path=path)
    if isinstance(value, list):
        return _sanitize_summary_list(value, path=path)
    if not isinstance(value, dict):
        return None
    return _sanitize_summary_dict(value, path=path)


def _sanitize_summary_scalar(value: Any, *, path: tuple[str, ...] = ()) -> Any:
    normalized = _scalar_or_none(value)
    leaf_key = path[-1] if path else ""
    if isinstance(normalized, str) and leaf_key in {"country", "countrycode", "registrationcountry", "messages"}:
        return normalized
    if isinstance(normalized, str) and not _is_meaningful_text(normalized):
        return None
    return normalized


def _sanitize_summary_list(value: list[Any], *, path: tuple[str, ...] = ()) -> list[Any] | None:
    sanitized_items = []
    for item in value:
        sanitized = _sanitize_summary_value(item, path=path)
        if sanitized not in (None, "", [], {}):
            sanitized_items.append(sanitized)
    return sanitized_items or None


def _sanitize_summary_dict(value: dict[str, Any], *, path: tuple[str, ...] = ()) -> dict[str, Any] | None:
    sanitized: dict[str, Any] = {}
    wrapper_values: list[Any] = []
    for key, child in value.items():
        normalized_key = _normalize_key(key)
        if _should_skip_report_field(key, child, path=path):
            continue
        child_path = path + ((normalized_key,) if normalized_key not in _NORMALIZED_REPORT_WRAPPER_KEYS else ())
        sanitized_child = _sanitize_summary_value(child, path=child_path)
        if sanitized_child in (None, "", [], {}):
            continue
        if normalized_key in _NORMALIZED_REPORT_WRAPPER_KEYS:
            wrapper_values.append(sanitized_child)
            continue
        sanitized[key] = sanitized_child
    if sanitized:
        for wrapper_value in wrapper_values:
            _merge_wrapper_evidence(sanitized, wrapper_value)
        return sanitized
    return _merge_wrapper_values(wrapper_values)


def _merge_wrapper_values(values: list[Any]) -> Any:
    if not values:
        return None
    if any(isinstance(value, dict) for value in values):
        merged: dict[str, Any] = {}
        scalar_values: list[Any] = []
        for value in values:
            if isinstance(value, dict):
                _merge_wrapper_evidence(merged, value)
            else:
                scalar_values.append(value)
        flattened_scalar_value = _flatten_wrapper_values(scalar_values)
        if flattened_scalar_value not in (None, "", [], {}):
            _merge_wrapper_evidence(merged, flattened_scalar_value)
        return merged or None
    return _flatten_wrapper_values(values)
