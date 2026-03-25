from __future__ import annotations

from typing import Any

from ._service_analysis_payload_support import _NORMALIZED_REPORT_WRAPPER_KEYS, _REPORT_MEANINGFUL_KEYWORDS


def _append_unique(items: list[dict[str, Any]], seen: set[str], value: dict[str, Any]) -> None:
    key = repr(_sorted_for_dedup(value))
    if key not in seen:
        seen.add(key)
        items.append(value)


def _sorted_for_dedup(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple((key, _normalize_source_for_dedup(item) if key == "source" else _sorted_for_dedup(item)) for key, item in sorted(value.items()))
    if isinstance(value, list):
        return tuple(_sorted_for_dedup(item) for item in value)
    return value


def _normalize_source_for_dedup(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().lower()
    return _sorted_for_dedup(value)


def _is_scalar_fact_value(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))


def _scalar_or_none(value: Any) -> str | int | float | bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        normalized = " ".join(value.split())
        return normalized or None
    return None


def _first_scalar(*values: Any) -> str | int | float | bool | None:
    for value in values:
        normalized = _scalar_or_none(value)
        if normalized not in (None, ""):
            return normalized
    return None


def _normalize_key(value: Any) -> str:
    return "".join(character for character in str(value or "").strip().lower() if character.isalnum())


def _display_label(value: str) -> str:
    compact = str(value or "").replace("_", " ").strip()
    return compact[:1].upper() + compact[1:] if compact else "Fact"


def _category_from_path(path: tuple[str, ...]) -> str | None:
    joined_path = " ".join(path)
    if "odometer" in joined_path or "rollback" in joined_path:
        return "mileage"
    for category in ("damage", "accident", "title", "salvage", "theft", "export", "import", "ownership", "mileage"):
        if category in joined_path:
            return category
    return None


def _is_meaningful_fact_key(key: str) -> bool:
    return any(keyword in _normalize_key(key) for keyword in _REPORT_MEANINGFUL_KEYWORDS)


def _contains_meaningful_keyword(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in _REPORT_MEANINGFUL_KEYWORDS)


def _is_meaningful_text(text: str) -> bool:
    normalized = " ".join(str(text).split())
    if not normalized:
        return False
    return normalized.lower() not in {"n/a", "none", "unknown", "not available", "no data"} and len(normalized) > 2


def _format_fact(key: str, value: Any) -> str | None:
    normalized_value = _scalar_or_none(value)
    return None if normalized_value in (None, "") else f"{_display_label(key)}: {normalized_value}"


def _is_negative_fact_value(value: Any) -> bool:
    normalized_value = _scalar_or_none(value)
    if normalized_value is False:
        return True
    if not isinstance(normalized_value, str):
        return False
    lowered = normalized_value.strip().lower()
    return lowered in {"false", "no"} or lowered.startswith("no ") or lowered.startswith("not ")


def _has_real_event_anchor(date_value: str | int | float | bool | None, mileage_value: str | int | float | bool | None, event_type: str | int | float | bool | None, label_value: str | int | float | bool | None) -> bool:
    return (date_value not in (None, "") or mileage_value not in (None, "")) and (event_type not in (None, "") or label_value not in (None, ""))


def _is_derivable_event_type(value: str) -> bool:
    normalized = _normalize_key(value)
    blocked = {"ownership", "owner", "title", "salvage", "rebuilt", "mileage", "odometer", "rollback", "country", "history"}
    if any(token in normalized for token in blocked):
        return False
    allowed = {"accident", "damage", "theft", "stolen", "import", "export", "sale", "auction", "registration", "inspection", "service", "repair", "incident", "loss", "flood", "fire"}
    return any(token in normalized for token in allowed)


def _direct_sibling_fact_values(value: dict[str, Any]) -> dict[str, Any]:
    return {
        normalized_key: value[key]
        for key in value
        if (normalized_key := _normalize_key(key)) not in _NORMALIZED_REPORT_WRAPPER_KEYS
    }


def _anchored_event_type(value: dict[str, Any], path: tuple[str, ...]) -> str | None:
    if path and _is_derivable_event_type(path[-1]):
        return path[-1]
    for key, item in value.items():
        normalized_key = _normalize_key(key)
        if _is_derivable_event_type(normalized_key) and _is_scalar_fact_value(item) and not _is_negative_fact_value(item):
            return normalized_key
    return None
