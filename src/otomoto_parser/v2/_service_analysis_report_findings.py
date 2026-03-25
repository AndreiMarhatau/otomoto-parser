from __future__ import annotations

from typing import Any

from ._service_analysis_payload_common import _compact_dict
from ._service_analysis_payload_support import _NORMALIZED_REPORT_WRAPPER_KEYS, _should_skip_report_field
from ._service_analysis_report_utils import _category_from_path, _contains_meaningful_keyword, _direct_sibling_fact_values, _display_label, _first_scalar, _is_derivable_event_type, _is_meaningful_fact_key, _is_meaningful_text, _is_negative_fact_value, _is_scalar_fact_value, _normalize_key, _scalar_or_none


def _extract_important_findings(value: Any, source_name: str, *, path: tuple[str, ...] = (), state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    current_state = dict(state or {})
    blocked_values = current_state.pop("__blocked_values__", {})
    if isinstance(value, dict):
        current_state = _with_record_context(current_state, value)
    if _is_scalar_fact_value(value):
        finding = _finding_from_scalar(source_name, path, value, current_state)
        return [finding] if finding is not None else []
    if isinstance(value, list):
        findings: list[dict[str, Any]] = []
        for child in value:
            findings.extend(_extract_important_findings(child, source_name, path=path, state={**current_state, "__blocked_values__": blocked_values}))
        return findings
    if not isinstance(value, dict):
        return []
    findings = []
    typed_evidence = _typed_record_finding(source_name, path, value, current_state)
    if typed_evidence is not None:
        findings.append(typed_evidence)
    sibling_values = _direct_sibling_fact_values(value)
    for key, child in value.items():
        normalized_key = _normalize_key(key)
        if normalized_key == "value" and path:
            findings.extend(_extract_important_findings(child, source_name, path=path, state={**current_state, "__blocked_values__": {}}))
            continue
        if _should_skip_report_field(key, child, path=path):
            continue
        findings.extend(
            _extract_findings_child(
                child,
                normalized_key,
                {
                    "source_name": source_name,
                    "path": path,
                    "current_state": current_state,
                    "blocked_values": blocked_values,
                    "sibling_values": sibling_values,
                },
            )
        )
    return findings


def _finding_from_scalar(source_name: str, path: tuple[str, ...], value: Any, context: dict[str, Any]) -> dict[str, Any] | None:
    normalized_value = _scalar_or_none(value)
    if normalized_value in (None, ""):
        return None
    leaf_key = _normalize_key(path[-1]) if path else ""
    if leaf_key in {"date", "eventdate", "lossdate", "mileage", "odometer", "odometerreading", "country", "countrycode", "registrationcountry", "type", "eventtype", "label", "description", "source", "provider"}:
        return None
    joined_path = " ".join(path)
    semantic_status = leaf_key == "status" and isinstance(context.get("event_type"), str)
    if not semantic_status and not _is_meaningful_fact_key(joined_path) and not (isinstance(normalized_value, str) and _contains_meaningful_keyword(normalized_value)):
        return None
    if _is_negative_fact_value(normalized_value) and any(_is_derivable_event_type(part) for part in path):
        return None
    if isinstance(normalized_value, str) and not _is_meaningful_text(normalized_value):
        return None
    key_name = path[-1] if path else "fact"
    category_path = path + ((context["event_type"],) if leaf_key == "status" and isinstance(context.get("event_type"), str) else ())
    return _compact_dict({"source": source_name, "category": _category_from_path(category_path), "label": _display_label(key_name), "value": normalized_value, "date": context.get("date"), "mileage": context.get("mileage"), "country": context.get("country")})


def _typed_record_finding(source_name: str, path: tuple[str, ...], value: dict[str, Any], context: dict[str, Any]) -> dict[str, Any] | None:
    event_type = _first_scalar(value.get("type"), value.get("eventType"), value.get("category"))
    description = _first_scalar(value.get("description"), value.get("label"), value.get("title"))
    date_value = _first_scalar(value.get("date"), value.get("eventDate"), value.get("lossDate"))
    mileage_value = _first_scalar(value.get("mileage"), value.get("odometer"), value.get("odometerReading"))
    if not isinstance(event_type, str) or not _is_derivable_event_type(event_type):
        return None
    if not isinstance(description, str) or not _is_meaningful_text(description):
        return None
    return _compact_dict(
        {
            "source": source_name,
            "category": _category_from_path(path + (_normalize_key(event_type),)),
            "label": _display_label(event_type),
            "value": description,
            "date": date_value or context.get("date"),
            "mileage": mileage_value if mileage_value not in (None, "") else context.get("mileage"),
            "country": _first_scalar(value.get("country"), value.get("countryCode"), value.get("registrationCountry")) or context.get("country"),
        }
    )


def _extract_findings_child(
    child: Any,
    normalized_key: str,
    branch_state: dict[str, Any],
) -> list[dict[str, Any]]:
    source_name = branch_state["source_name"]
    path = branch_state["path"]
    current_state = branch_state["current_state"]
    blocked_values = branch_state["blocked_values"]
    sibling_values = branch_state["sibling_values"]
    child_path = path + ((normalized_key,) if normalized_key not in _NORMALIZED_REPORT_WRAPPER_KEYS else ())
    if normalized_key in blocked_values:
        blocked_child = blocked_values[normalized_key]
        if isinstance(child, dict) and isinstance(blocked_child, dict):
            return _extract_important_findings(child, source_name, path=child_path, state={**current_state, "__blocked_values__": _direct_sibling_fact_values(blocked_child)})
        if isinstance(child, dict):
            return _extract_important_findings(child, source_name, path=child_path, state={**current_state, "__blocked_values__": {"value": blocked_child}})
        if isinstance(blocked_child, dict):
            merged_state = _merge_finding_context(current_state, blocked_child)
            return _extract_important_findings(child, source_name, path=child_path, state={**merged_state, "__blocked_values__": {}}) + _extract_important_findings(blocked_child, source_name, path=child_path, state={**merged_state, "__blocked_values__": {}})
        return _extract_important_findings(child, source_name, path=child_path, state={**_merge_finding_context(current_state, blocked_child), "__blocked_values__": {}})
    child_blocked_values = sibling_values if normalized_key in _NORMALIZED_REPORT_WRAPPER_KEYS else {}
    return _extract_important_findings(child, source_name, path=child_path, state={**current_state, "__blocked_values__": child_blocked_values})


def _merge_finding_context(context: dict[str, Any], value: Any) -> dict[str, Any]:
    merged = dict(context)
    if isinstance(value, dict):
        for candidates, target_key in (
            (("date", "eventDate", "lossDate"), "date"),
            (("mileage", "odometer", "odometerReading"), "mileage"),
            (("country", "countryCode", "registrationCountry"), "country"),
        ):
            candidate = _first_scalar(*(value.get(source_key) for source_key in candidates))
            if candidate not in (None, ""):
                merged[target_key] = candidate
    return merged


def _with_record_context(context: dict[str, Any], value: dict[str, Any]) -> dict[str, Any]:
    merged = _merge_finding_context(context, value)
    event_type = _first_scalar(value.get("type"), value.get("eventType"), value.get("category"))
    if isinstance(event_type, str) and _is_derivable_event_type(event_type):
        merged["event_type"] = _normalize_key(event_type)
    return merged
