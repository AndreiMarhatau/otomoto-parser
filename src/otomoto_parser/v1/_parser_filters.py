from __future__ import annotations

from urllib.parse import parse_qsl, urlparse

from ._parser_common import (
    CATEGORY_SLUG_TO_ID,
    DEFAULT_EXPERIMENTS,
    DEFAULT_PARAMETERS,
    DEFAULT_SORT_BY,
    PERSISTED_QUERY_HASH,
    REGION_SLUG_TO_ID,
)


def _segment_body_types(segment: str) -> list[str]:
    if "seg-" not in segment:
        return []
    return [part[len("seg-") :] for part in segment.split("--") if part.startswith("seg-")]


def _parse_filters_from_url(url: str) -> tuple[list[dict[str, str]], str, int, set[str]]:
    parsed = urlparse(url)
    filters: list[dict[str, str]] = []
    sort_by = DEFAULT_SORT_BY
    start_page = 1
    inferred_names: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    seen_names: set[str] = set()

    def add_filter(name: str, value: str) -> None:
        if not name or value == "" or (name, value) in seen_pairs:
            return
        seen_pairs.add((name, value))
        seen_names.add(name)
        filters.append({"name": name, "value": value})

    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key == "page" and value:
            start_page = _parse_page(value, start_page)
            continue
        if not key.startswith("search["):
            continue
        name = _query_name(key)
        if name == "order" and value:
            sort_by = value
            continue
        if name == "page" and value:
            start_page = _parse_page(value, start_page)
            continue
        add_filter(name, value)

    remaining = _path_filters(parsed.path.split("/"), add_filter, seen_names)
    if remaining:
        _add_make_model_filters(remaining, add_filter, seen_names, inferred_names)
    return filters, sort_by, start_page, inferred_names


def _parse_page(value: str, default: int) -> int:
    try:
        return int(value)
    except ValueError:
        return default


def _query_name(key: str) -> str:
    name = key[len("search[") :]
    if name.endswith("]"):
        name = name[:-1]
    if "][" in name:
        name = name.split("][", 1)[0]
    return name


def _path_filters(segments: list[str], add_filter, seen_names: set[str]) -> list[str]:
    clean_segments = [segment for segment in segments if segment]
    category_slug = clean_segments[0] if clean_segments else None
    if category_slug and "category_id" not in seen_names:
        category_id = CATEGORY_SLUG_TO_ID.get(category_slug)
        if category_id:
            add_filter("category_id", category_id)

    remaining: list[str] = []
    for segment in clean_segments[1:]:
        body_types = _segment_body_types(segment)
        if body_types:
            for body_type in body_types:
                add_filter("filter_enum_body_type", body_type)
        elif segment.startswith("od-") and "filter_float_year:from" not in seen_names:
            add_filter("filter_float_year:from", segment[len("od-") :])
        elif segment.startswith("do-") and "filter_float_year:to" not in seen_names:
            add_filter("filter_float_year:to", segment[len("do-") :])
        elif (region_id := REGION_SLUG_TO_ID.get(segment)) and "region_id" not in seen_names:
            add_filter("region_id", region_id)
        else:
            remaining.append(segment)
    return remaining


def _add_make_model_filters(
    remaining: list[str],
    add_filter,
    seen_names: set[str],
    inferred_names: set[str],
) -> None:
    if "filter_enum_make" not in seen_names:
        add_filter("filter_enum_make", remaining[0])
        inferred_names.add("filter_enum_make")
    if len(remaining) > 1 and "filter_enum_model" not in seen_names:
        add_filter("filter_enum_model", remaining[1])
        inferred_names.add("filter_enum_model")


def _build_payload(filters: list[dict[str, str]], sort_by: str, page: int) -> dict:
    return {
        "extensions": {"persistedQuery": {"sha256Hash": PERSISTED_QUERY_HASH, "version": 1}},
        "operationName": "listingScreen",
        "variables": {
            "after": None,
            "experiments": DEFAULT_EXPERIMENTS,
            "filters": filters,
            "includeCepik": True,
            "includeFiltersCounters": False,
            "includeNewPromotedAds": False,
            "includePriceEvaluation": True,
            "includePromotedAds": False,
            "includeRatings": False,
            "includeSortOptions": False,
            "includeSuggestedFilters": False,
            "maxAge": 60,
            "page": page,
            "parameters": DEFAULT_PARAMETERS,
            "promotedInput": {},
            "searchTerms": [],
            "sortBy": sort_by or DEFAULT_SORT_BY,
        },
    }
