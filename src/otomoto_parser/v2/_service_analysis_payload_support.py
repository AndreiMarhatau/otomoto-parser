from __future__ import annotations

from typing import Any

_LISTING_PARAMETER_FIELDS = (
    ("make", "make"),
    ("model", "model"),
    ("version", "version"),
    ("generation", "generation"),
    ("year", "year"),
    ("mileage", "mileage"),
    ("fuel_type", "fuelType"),
    ("gearbox", "gearbox"),
    ("body_type", "bodyType"),
    ("engine_capacity", "engineCapacity"),
    ("engine_power", "enginePower"),
    ("drive", "drive"),
    ("doors_no", "doors"),
    ("seats_no", "seats"),
    ("color", "color"),
    ("registered", "registered"),
    ("country_origin", "countryOfOrigin"),
    ("condition", "condition"),
    ("origin_country", "countryOfOrigin"),
)
_IDENTIFIER_PARAMETER_ALIASES = {"vin": "vin", "registration": "registrationNumber", "date_registration": "firstRegistrationDate"}
_MAX_SHORT_DESCRIPTION_LENGTH = 600
_MAX_DESCRIPTION_LENGTH = 3000
_MAX_TIMELINE_EVENTS = 8
_MAX_TIMELINE_EVENT_FIELDS = ("date", "type", "label", "mileage", "country", "source")
_REPORT_IDENTIFIER_FIELDS = ("vin_number", "registration_number", "first_registration_date", "api_version")
_REPORT_MEANINGFUL_KEYWORDS = ("accident", "damage", "ownership", "owner", "mileage", "odometer", "rollback", "inconsist", "discrep", "title", "salvage", "rebuilt", "theft", "stolen", "export", "import", "country", "auction", "loss", "flood", "fire", "history")
_REPORT_WRAPPER_KEYS = {"autodna_data", "carfax_data", "technical_data", "technicalData", "timeline_data", "timelineData", "summary", "data", "response", "payload", "wrapper", "result", "results", "report", "reports"}
_REPORT_META_KEYS = {"api_version", "cache", "cached", "cached_at", "cache_at", "cache_date", "created_at", "downloaded_at", "fetched_at", "generated_at", "last_attempt_at", "last_updated", "lookup", "lookup_options", "metadata", "raw", "request_id", "retrieved_at", "snapshot_id", "timestamp", "updated_at"}
def _normalize_report_key(value: Any) -> str:
    return "".join(character for character in str(value or "").strip().lower() if character.isalnum())
_NORMALIZED_REPORT_WRAPPER_KEYS = {_normalize_report_key(key) for key in _REPORT_WRAPPER_KEYS}
_NORMALIZED_REPORT_META_KEYS = {_normalize_report_key(key) for key in _REPORT_META_KEYS}
def _should_skip_report_field(key: Any, value: Any, *, path: tuple[str, ...] = ()) -> bool:
    normalized_key = _normalize_report_key(key)
    if normalized_key in _NORMALIZED_REPORT_META_KEYS:
        return True
    if normalized_key != "status":
        return False
    if isinstance(value, (dict, list)):
        return True
    if not path:
        return _is_transport_status_value(value)
    return path[-1] in _NORMALIZED_REPORT_WRAPPER_KEYS


def _is_transport_status_value(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in {"success", "ok", "ready", "pending", "running", "failed", "failure", "error", "completed", "cancelled", "cancelling", "processing", "inprogress"}
def _flatten_wrapper_values(values: list[Any]) -> Any:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    if all(isinstance(value, list) for value in values):
        flattened: list[Any] = []
        for value in values:
            flattened.extend(value)
        return flattened or None
    return values
def _merge_wrapper_evidence(target: dict[str, Any], value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            target_key = _existing_wrapper_key(target, key)
            if target_key in target:
                _merge_wrapper_key(target, target_key, child)
            else:
                target[key] = child
        return
    key = "messages" if isinstance(value, str) or (isinstance(value, list) and all(isinstance(item, str) for item in value)) else "items"
    if isinstance(value, list):
        if key in target and isinstance(target[key], list):
            target[key].extend(value)
        elif key not in target:
            target[key] = list(value)
        else:
            target[key] = [target[key], *value]
        return
    if key in target and isinstance(target[key], list):
        target[key].append(value)
    elif key not in target:
        target[key] = [value] if key == "messages" else value
    else:
        target[key] = [target[key], value]
def _existing_wrapper_key(target: dict[str, Any], key: str) -> str:
    normalized_key = _normalize_report_key(key)
    for existing_key in target:
        if _normalize_report_key(existing_key) == normalized_key:
            return existing_key
    return key
def _is_wrapper_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))
def _merge_wrapper_key(target: dict[str, Any], key: str, child: Any) -> None:
    existing = target[key]
    if isinstance(existing, dict) and isinstance(child, dict):
        if _is_wrapper_scalar(child.get("value")):
            _merge_wrapper_evidence(existing, _wrapper_conflict_payload(child["value"]))
        _merge_wrapper_evidence(existing, {nested_key: nested_value for nested_key, nested_value in child.items() if nested_key != "value"})
        return
    if _is_wrapper_scalar(existing) and isinstance(child, dict):
        target[key] = {"value": existing}
        _merge_wrapper_evidence(target[key], _wrapper_conflict_payload(child.get("value")) if _is_wrapper_scalar(child.get("value")) else {})
        _merge_wrapper_evidence(target[key], {nested_key: nested_value for nested_key, nested_value in child.items() if nested_key != "value"})
        return
    if _is_wrapper_scalar(existing):
        target[key] = {"value": existing, **_wrapper_conflict_payload(child)}
        return
    if isinstance(existing, dict):
        if _is_wrapper_scalar(child) and _is_wrapper_scalar(existing.get("value")):
            _merge_wrapper_evidence(existing, _wrapper_conflict_payload(child))
            return
        merge_key = "value" if _is_wrapper_scalar(child) else _wrapper_collection_key(child)
        _merge_wrapper_evidence(existing, {merge_key: child})
        return
    if isinstance(existing, list) and isinstance(child, list):
        existing.extend(child)
        return
    if isinstance(existing, list):
        existing.append(child)
        return
def _wrapper_collection_key(value: Any) -> str:
    return "messages" if isinstance(value, list) and all(isinstance(item, str) for item in value) else "items"
def _wrapper_conflict_payload(value: Any) -> dict[str, Any]:
    if _is_wrapper_scalar(value):
        return {"messages" if isinstance(value, str) else "items": [value]}
    key = _wrapper_collection_key(value)
    return {key: list(value) if isinstance(value, list) else [value]}
def _technical_data_root(report: dict[str, Any]) -> dict[str, Any]:
    technical_data = report.get("technical_data")
    if not isinstance(technical_data, dict):
        return {}
    return technical_data.get("technicalData") if isinstance(technical_data.get("technicalData"), dict) else {}
def _source_status_payload(report_payload: dict[str, Any], report: dict[str, Any], compact_dict: Any) -> dict[str, Any]:
    summary = report_payload.get("summary") if isinstance(report_payload.get("summary"), dict) else {}
    return compact_dict(
        {
            "apiVersion": report.get("api_version"),
            "autodnaAvailable": summary.get("autodnaAvailable"),
            "carfaxAvailable": summary.get("carfaxAvailable"),
            "autodnaUnavailable": summary.get("autodnaUnavailable"),
            "carfaxUnavailable": summary.get("carfaxUnavailable"),
        }
    )
def _technical_summary_payload(basic_data: dict[str, Any], ownership_history: dict[str, Any], compact_dict: Any) -> dict[str, Any]:
    return compact_dict(
        {
            "basicData": compact_dict({"make": basic_data.get("make"), "model": basic_data.get("model"), "type": basic_data.get("type"), "modelYear": basic_data.get("modelYear"), "fuel": basic_data.get("fuel"), "engineCapacity": basic_data.get("engineCapacity"), "enginePower": basic_data.get("enginePower"), "bodyType": basic_data.get("bodyType"), "color": basic_data.get("color")}),
            "ownershipHistory": compact_dict({"numberOfOwners": ownership_history.get("numberOfOwners"), "numberOfCoowners": ownership_history.get("numberOfCoowners"), "dateOfLastOwnershipChange": ownership_history.get("dateOfLastOwnershipChange")}),
        }
    )
