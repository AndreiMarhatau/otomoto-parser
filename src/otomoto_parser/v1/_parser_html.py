from __future__ import annotations

import json
import re
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ._parser_common import GRAPHQL_ENDPOINT, LOGGER, _normalize_start_url, _url_with_page
from ._parser_retry import RetryPolicy, _with_retry


def _post_graphql(payload: dict, headers: dict[str, str], timeout_s: float) -> dict:
    request = Request(GRAPHQL_ENDPOINT, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urlopen(request, timeout=timeout_s) as response:
        parsed = json.loads(response.read().decode("utf-8"))
    if "errors" in parsed:
        raise RuntimeError(f"GraphQL errors: {parsed['errors']}")
    return parsed


def _iter_embedded_json_values(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _iter_embedded_json_values(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_embedded_json_values(item)
    elif isinstance(value, str) and value[:1] in {"{", "["}:
        try:
            yield from _iter_embedded_json_values(json.loads(value))
        except json.JSONDecodeError:
            return


def _extract_canonical_filter_mappings(html: str, target_names: set[str]) -> dict[tuple[str, str], str]:
    next_data = _extract_next_data(html)
    if next_data is None:
        return {}
    mappings: dict[tuple[str, str], str] = {}
    for item in _iter_embedded_json_values(next_data):
        if item.get("name") in target_names and isinstance(item.get("value"), str) and isinstance(item.get("canonical"), str):
            mappings[(item["name"], item["canonical"])] = item["value"]
    return mappings


def _extract_search_page_total_count(html: str) -> int | None:
    next_data = _extract_next_data(html)
    if next_data is None:
        return None
    for item in _iter_embedded_json_values(next_data):
        if "advertSearch" in item and isinstance(item["advertSearch"], dict):
            total_count = item["advertSearch"].get("totalCount")
            if isinstance(total_count, int):
                return total_count
        if "appliedFilters" in item and isinstance(item.get("totalCount"), int):
            return item["totalCount"]
    return None


def _extract_applied_filters(html: str) -> list[dict[str, str]]:
    next_data = _extract_next_data(html)
    if next_data is None:
        return []
    for item in _iter_embedded_json_values(next_data):
        advert_search = item.get("advertSearch") if isinstance(item, dict) else None
        if not isinstance(advert_search, dict) or not isinstance(advert_search.get("appliedFilters"), list):
            continue
        result = [_applied_filter(candidate) for candidate in advert_search["appliedFilters"]]
        result = [candidate for candidate in result if candidate is not None]
        if result:
            return result
    return []


def _applied_filter(candidate: Any) -> dict[str, str] | None:
    if not isinstance(candidate, dict):
        return None
    name = candidate.get("name")
    value = candidate.get("value")
    canonical = candidate.get("canonical")
    if all(isinstance(field, str) for field in (name, value, canonical)):
        return {"name": name, "value": value, "canonical": canonical}
    return None


def _extract_next_data(html: str) -> dict[str, Any] | None:
    match = re.search(
        r'<script\b(?=[^>]*\bid=["\']__NEXT_DATA__["\'])(?=[^>]*\btype=["\']application/json["\'])[^>]*>(?P<body>.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return None
    try:
        return json.loads(match.group("body"))
    except json.JSONDecodeError:
        return None


def _fetch_page_text(url: str, headers: dict[str, str], timeout_s: float) -> str:
    with urlopen(Request(url, headers=headers, method="GET"), timeout=timeout_s) as response:
        return response.read().decode("utf-8")


def _resolve_canonical_make_model_filters(
    url: str,
    filters: list[dict[str, str]],
    inferred_names: set[str],
    resolution: dict[str, Any],
) -> tuple[list[dict[str, str]], bool, int | None]:
    if not any(item.get("name") in {"filter_enum_make", "filter_enum_model"} for item in filters):
        return filters, False, None
    page_request = resolution.get("page_request_func") or _fetch_page_text
    try:
        html = _with_retry(
            lambda: page_request(_url_with_page(_normalize_start_url(url), 1), resolution["headers"], resolution["timeout_s"]),
            RetryPolicy(attempts=max(1, resolution.get("retry_attempts", 1)), base_delay=resolution.get("backoff_base", 0.0)),
            label="search page fetch",
            logger=LOGGER,
        )
    except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, RuntimeError) as exc:
        LOGGER.warning(
            "Could not resolve canonical make/model filters from page HTML (%s: %s). Continuing with URL values.",
            exc.__class__.__name__,
            str(exc),
        )
        return filters, True, None
    return _resolved_filters(filters, inferred_names, html), False, _extract_search_page_total_count(html)


def _resolved_filters(filters: list[dict[str, str]], inferred_names: set[str], html: str) -> list[dict[str, str]]:
    mappings = _extract_canonical_filter_mappings(html, {item["name"] for item in filters if isinstance(item.get("name"), str)})
    applied_filters = _extract_applied_filters(html)
    resolved_filters = [dict(item) for item in filters]
    seen_names = {item["name"] for item in resolved_filters}
    seen_pairs = {(item["name"], item["value"]) for item in resolved_filters}
    for item in resolved_filters:
        resolved_value = mappings.get((item["name"], item["value"]))
        if resolved_value:
            item["value"] = resolved_value
            seen_pairs.add((item["name"], item["value"]))
        elif item["name"] in inferred_names:
            _replace_inferred_filter(item, applied_filters, seen_names, seen_pairs)
    for candidate in applied_filters:
        pair = (candidate["name"], candidate["value"])
        if pair not in seen_pairs:
            resolved_filters.append({"name": candidate["name"], "value": candidate["value"]})
            seen_names.add(candidate["name"])
            seen_pairs.add(pair)
    return resolved_filters


def _replace_inferred_filter(
    item: dict[str, str],
    applied_filters: list[dict[str, str]],
    seen_names: set[str],
    seen_pairs: set[tuple[str, str]],
) -> None:
    for candidate in applied_filters:
        if candidate["canonical"] != item["value"]:
            continue
        if candidate["name"] != item["name"] and candidate["name"] in seen_names:
            continue
        seen_names.discard(item["name"])
        item["name"] = candidate["name"]
        item["value"] = candidate["value"]
        seen_names.add(item["name"])
        seen_pairs.add((item["name"], item["value"]))
        break
