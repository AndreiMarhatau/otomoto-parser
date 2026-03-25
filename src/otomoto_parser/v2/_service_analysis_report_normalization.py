from __future__ import annotations

from typing import Any

from ._service_analysis_payload_common import _compact_dict
from ._service_analysis_report_findings import _extract_important_findings
from ._service_analysis_payload_support import _NORMALIZED_REPORT_WRAPPER_KEYS, _should_skip_report_field
from ._service_analysis_report_utils import _anchored_event_type, _append_unique, _direct_sibling_fact_values, _first_scalar, _format_fact, _has_real_event_anchor, _is_derivable_event_type, _is_meaningful_fact_key, _is_negative_fact_value, _is_scalar_fact_value, _normalize_key
def _history_events_payload(report: dict[str, Any]) -> list[dict[str, Any]] | None:
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    timeline_data = report.get("timeline_data")
    if isinstance(timeline_data, dict):
        timeline_root = timeline_data.get("timelineData")
        timeline_events = timeline_root.get("events") if isinstance(timeline_root, dict) else None
        if isinstance(timeline_events, list):
            for event in timeline_events:
                normalized = _typed_history_event(_normalize_history_event(event, source="timeline"))
                if normalized is not None:
                    _append_unique(events, seen, normalized)
    for source_name in ("autodna", "carfax"):
        provider_data = report.get(f"{source_name}_data")
        if isinstance(provider_data, dict):
            for event in _extract_provider_events(provider_data, source_name):
                _append_unique(events, seen, event)
    return events or None
def _report_summaries_payload(report: dict[str, Any]) -> list[dict[str, Any]] | None:
    summaries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source_name in ("autodna", "carfax"):
        provider_data = report.get(f"{source_name}_data")
        if not isinstance(provider_data, dict):
            continue
        for item in _extract_summary_items(provider_data.get("summary"), source_name):
            _append_unique(summaries, seen, item)
    return summaries or None
def _important_findings_payload(report: dict[str, Any]) -> list[dict[str, Any]] | None:
    findings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source_name in ("autodna", "carfax"):
        provider_data = report.get(f"{source_name}_data")
        if not isinstance(provider_data, dict):
            continue
        for finding in _extract_important_findings(provider_data, source_name):
            _append_unique(findings, seen, finding)
    return findings or None
def _extract_provider_events(value: Any, source_name: str, *, path: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    if isinstance(value, list):
        events: list[dict[str, Any]] = []
        for item in value:
            normalized = _typed_history_event(_normalize_history_event(item, source=source_name, path=path), path)
            if normalized is not None:
                events.append(normalized)
                continue
            events.extend(_extract_provider_events(item, source_name, path=path))
        return events
    if not isinstance(value, dict):
        return []
    current_event = _typed_history_event(_normalize_history_event(value, source=source_name, path=path), path)
    if current_event is not None:
        return [current_event]
    anchored_event = _event_from_anchored_facts(value, path, source_name)
    if anchored_event is not None:
        return [anchored_event]
    events = []
    for key, child in value.items():
        normalized_key = _normalize_key(key)
        if _should_skip_report_field(key, child, path=path):
            continue
        child_path = path + ((normalized_key,) if normalized_key not in _NORMALIZED_REPORT_WRAPPER_KEYS else ())
        normalized = _typed_history_event(_normalize_history_event(child, source=source_name, path=child_path), child_path)
        if normalized is not None:
            events.append(normalized)
            continue
        events.extend(_extract_provider_events(child, source_name, path=child_path))
    return events
def _normalize_history_event(value: Any, *, source: str, path: tuple[str, ...] = ()) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    date_value = _first_scalar(value.get("date"), value.get("eventDate"), value.get("lossDate"))
    mileage_value = _first_scalar(value.get("mileage"), value.get("odometer"), value.get("odometerReading"))
    country_value = _first_scalar(value.get("country"), value.get("countryCode"), value.get("registrationCountry"))
    source_value = _first_scalar(value.get("source"), value.get("provider")) or source
    event_type = _first_scalar(value.get("type"), value.get("eventType"), value.get("category"))
    label_value = _first_scalar(value.get("label"), value.get("description"), value.get("title"))
    detail_path = path
    if not (detail_path and _is_derivable_event_type(detail_path[-1])) and isinstance(event_type, str) and _is_derivable_event_type(event_type):
        detail_path = (_normalize_key(event_type),)
    facts = _event_detail_facts(value, detail_path)
    if not _has_real_event_anchor(date_value, mileage_value, event_type, label_value):
        return None
    return _compact_dict({"date": date_value, "type": event_type, "label": label_value, "mileage": mileage_value, "country": country_value, "source": source_value, "details": facts})
def _typed_history_event(event: dict[str, Any] | None, path: tuple[str, ...] = ()) -> dict[str, Any] | None:
    if event is None:
        return None
    event_type = _first_scalar(event.get("type"))
    if event_type not in (None, ""):
        return _compact_dict(event)
    fallback_type = path[-1] if path else None
    if fallback_type in (None, "") or not _is_derivable_event_type(str(fallback_type)):
        return None
    typed_event = dict(event)
    typed_event["type"] = fallback_type
    return _compact_dict(typed_event)
def _event_detail_facts(value: dict[str, Any], path: tuple[str, ...] = ()) -> list[str] | None:
    details: list[str] = []
    seen: set[str] = set()
    skip_keys = {"date", "eventdate", "lossdate", "mileage", "odometer", "odometerreading", "country", "countrycode", "registrationcountry", "source", "provider", "type", "eventtype", "category", "label", "description", "title"}
    for key, item in value.items():
        normalized_key = _normalize_key(key)
        if normalized_key in skip_keys or _should_skip_report_field(key, item):
            continue
        include_status = normalized_key == "status" and path and _is_derivable_event_type(path[-1])
        if (include_status or _is_meaningful_fact_key(normalized_key)) and _is_scalar_fact_value(item) and not _is_negative_fact_value(item):
            fact = _format_fact(normalized_key, item)
            if fact is not None and fact not in seen:
                seen.add(fact)
                details.append(fact)
    return details or None
def _extract_summary_items(value: Any, source_name: str, *, path: tuple[str, ...] = (), blocked_values: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if _is_scalar_fact_value(value):
        item = _summary_item_from_scalar(source_name, path, value)
        return [item] if item is not None else []
    if isinstance(value, list):
        items: list[dict[str, Any]] = []
        for child in value:
            items.extend(_extract_summary_items(child, source_name, path=path, blocked_values=blocked_values))
        return items
    if not isinstance(value, dict):
        return []
    if _summary_dict_is_event_evidence(value, source_name, path):
        return []
    items = []
    current_blocked_values = blocked_values or {}
    sibling_values = _direct_sibling_fact_values(value)
    for key, child in value.items():
        normalized_key = _normalize_key(key)
        items.extend(_extract_summary_child_items(key, child, normalized_key, {"source_name": source_name, "path": path, "current_blocked_values": current_blocked_values, "sibling_values": sibling_values}))
    return items
def _summary_item_from_scalar(source_name: str, path: tuple[str, ...], value: Any) -> dict[str, Any] | None:
    from ._service_analysis_report_utils import _category_from_path, _display_label, _is_meaningful_text, _scalar_or_none
    normalized_value = _scalar_or_none(value)
    if normalized_value in (None, ""):
        return None
    if not path:
        return None
    leaf_key = path[-1] if path else ""
    if leaf_key in {"date", "eventdate", "lossdate", "mileage", "odometer", "odometerreading", "country", "countrycode", "registrationcountry", "source", "provider"}:
        return None
    joined_path = " ".join(path)
    if isinstance(normalized_value, str) and not joined_path and len(normalized_value.split()) < 2:
        return None
    if not joined_path and not isinstance(normalized_value, str):
        return None
    if isinstance(normalized_value, str) and leaf_key != "messages" and not _is_meaningful_text(normalized_value.strip()):
        return None
    return _compact_dict({"source": source_name, "label": _display_label(path[-1]) if path else "summary", "category": _category_from_path(path), "value": normalized_value})
def _summary_dict_is_event_evidence(value: dict[str, Any], source_name: str, path: tuple[str, ...]) -> bool:
    return _typed_history_event(_normalize_history_event(value, source=source_name, path=path), path) is not None or _event_from_anchored_facts(value, path, source_name) is not None
def _extract_summary_child_items(
    key: Any,
    child: Any,
    normalized_key: str,
    branch_state: dict[str, Any],
) -> list[dict[str, Any]]:
    source_name = branch_state["source_name"]
    path = branch_state["path"]
    current_blocked_values = branch_state["current_blocked_values"]
    sibling_values = branch_state["sibling_values"]
    if normalized_key == "value" and path:
        return _extract_summary_items(child, source_name, path=path)
    if _should_skip_report_field(key, child, path=path):
        return []
    child_path = path + ((normalized_key,) if normalized_key not in _NORMALIZED_REPORT_WRAPPER_KEYS else ())
    if normalized_key in current_blocked_values:
        return _extract_blocked_summary_items(child, current_blocked_values[normalized_key], source_name, child_path)
    child_blocked_values = sibling_values if normalized_key in _NORMALIZED_REPORT_WRAPPER_KEYS else None
    return _extract_summary_items(child, source_name, path=child_path, blocked_values=child_blocked_values)
def _extract_blocked_summary_items(child: Any, blocked_child: Any, source_name: str, child_path: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(child, dict) and isinstance(blocked_child, dict):
        return _extract_summary_items(child, source_name, path=child_path, blocked_values=_direct_sibling_fact_values(blocked_child))
    if isinstance(child, dict):
        return _extract_summary_items(child, source_name, path=child_path, blocked_values={"value": blocked_child})
    if not isinstance(blocked_child, dict):
        return _extract_summary_items(child, source_name, path=child_path)
    return _extract_summary_items(child, source_name, path=child_path) + _extract_summary_items(blocked_child.get("value"), source_name, path=child_path) + _extract_summary_items({key: value for key, value in blocked_child.items() if key != "value"}, source_name, path=child_path)
def _event_from_anchored_facts(value: dict[str, Any], path: tuple[str, ...], source_name: str) -> dict[str, Any] | None:
    date_value = _first_scalar(value.get("date"), value.get("eventDate"), value.get("lossDate"))
    mileage_value = _first_scalar(value.get("mileage"), value.get("odometer"), value.get("odometerReading"))
    if date_value in (None, "") and mileage_value in (None, ""):
        return None
    event_type = _anchored_event_type(value, path)
    if event_type in (None, "") or not _is_derivable_event_type(str(event_type)):
        return None
    facts = _event_detail_facts(value, path)
    if not facts:
        return None
    return _compact_dict({"date": date_value, "type": event_type, "mileage": mileage_value, "country": _first_scalar(value.get("country"), value.get("countryCode"), value.get("registrationCountry")), "source": _first_scalar(value.get("source"), value.get("provider")) or source_name, "details": facts})
