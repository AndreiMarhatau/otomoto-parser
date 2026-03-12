from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

LOGGER = logging.getLogger("otomoto_parser")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)
DEFAULT_ACCEPT_LANGUAGE = "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"

RUN_MODE_RESUME = "resume"
RUN_MODE_APPEND_NEWER = "append-newer"
RUN_MODE_FULL = "full"
RUN_MODES = {RUN_MODE_RESUME, RUN_MODE_APPEND_NEWER, RUN_MODE_FULL}

GRAPHQL_ENDPOINT = "https://www.otomoto.pl/graphql"
PERSISTED_QUERY_HASH = "e78bd5939b000e39e9f2ca157b3068e014d4036b7e4af4c05086dd2c185f7a93"
DEFAULT_EXPERIMENTS = [
    {"key": "MCTA-1463", "variant": "a"},
    {"key": "CARS-79025", "variant": "a"},
    {"key": "CARS-79026", "variant": "a"},
    {"key": "CARS-64661", "variant": "b"},
]
DEFAULT_PARAMETERS = [
    "make",
    "offer_type",
    "show_pir",
    "fuel_type",
    "gearbox",
    "body_type",
    "country_origin",
    "registered",
    "mileage",
    "engine_capacity",
    "engine_code",
    "engine_power",
    "first_registration_year",
    "model",
    "version",
    "year",
]
DEFAULT_SORT_BY = "created_at_first:desc"

CATEGORY_SLUG_TO_ID = {
    "osobowe": "29",
}

REGION_SLUG_TO_ID = {
    "dolnoslaskie": "3",
    "kujawsko-pomorskie": "15",
    "lubelskie": "8",
    "lubuskie": "9",
    "lodzkie": "7",
    "malopolskie": "4",
    "mazowieckie": "2",
    "opolskie": "12",
    "podkarpackie": "17",
    "podlaskie": "18",
    "pomorskie": "5",
    "slaskie": "6",
    "swietokrzyskie": "13",
    "warminsko-mazurskie": "14",
    "wielkopolskie": "1",
    "zachodniopomorskie": "11",
}


@dataclass
class ParserState:
    start_url: str
    next_page: int
    pages_completed: int
    results_written: int
    has_more: bool = True

    @property
    def next_url(self) -> str:
        return _url_with_page(self.start_url, self.next_page)


ProgressCallback = Callable[[dict[str, Any]], None]


def _normalize_start_url(url: str) -> str:
    parsed = urlparse(url)
    query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key == "page" or key == "search[page]":
            continue
        query.append((key, value))
    normalized = parsed._replace(query=urlencode(query, doseq=True), fragment="")
    return urlunparse(normalized)


def _url_with_page(url: str, page: int) -> str:
    parsed = urlparse(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "page"]
    if page > 1:
        query.append(("page", str(page)))
    normalized = parsed._replace(query=urlencode(query, doseq=True), fragment="")
    return urlunparse(normalized)


def build_run_paths(start_url: str, output_dir: str | Path = "runs") -> tuple[Path, Path, Path]:
    run_root = Path(output_dir)
    normalized = _normalize_start_url(start_url)
    parsed = urlparse(normalized)
    base_name = f"{parsed.netloc}-{parsed.path.strip('/') or 'root'}"
    base_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", base_name).strip("-").lower()
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10]
    run_dir = run_root / f"{base_name}-{digest}"
    return run_dir, run_dir / "results.jsonl", run_dir / "state.json"


def _page_from_url(url: str) -> int:
    parsed = urlparse(url)
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key == "page" and value:
            try:
                return int(value)
            except ValueError:
                break
    return 1


def _read_state(state_path: Path) -> ParserState | None:
    if not state_path.exists():
        return None
    data = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    start_url = data.get("start_url")
    next_page = data.get("next_page")
    pages_completed = data.get("pages_completed", 0)
    results_written = data.get("results_written", 0)
    has_more = data.get("has_more", True)
    if not isinstance(start_url, str):
        return None
    if not isinstance(next_page, int):
        next_url = data.get("next_url")
        pending_next = bool(data.get("pending_next", False))
        if isinstance(next_url, str):
            page = _page_from_url(next_url)
            next_page = page + 1 if pending_next else page
        else:
            return None
    return ParserState(
        start_url=start_url,
        next_page=next_page,
        pages_completed=int(pages_completed),
        results_written=int(results_written),
        has_more=bool(has_more),
    )


def _write_state(state_path: Path, state: ParserState) -> None:
    payload = {
        "start_url": state.start_url,
        "next_page": state.next_page,
        "pages_completed": state.pages_completed,
        "results_written": state.results_written,
        "has_more": state.has_more,
    }
    state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


T = TypeVar("T")


def _with_retry(
    action: Callable[[], T],
    *,
    attempts: int,
    base_delay: float,
    label: str | None = None,
    logger: logging.Logger | None = None,
) -> T:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return action()
        except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
            last_error = exc
            if attempt == attempts - 1:
                break
            delay = base_delay * (2**attempt)
            if logger and label:
                logger.warning(
                    "Retrying %s after error (%s: %s). Attempt %s/%s in %.2fs.",
                    label,
                    exc.__class__.__name__,
                    str(exc),
                    attempt + 1,
                    attempts,
                    delay,
                )
            time.sleep(delay)
    if last_error:
        raise last_error
    raise RuntimeError("Retry failed without exception")


def _segment_body_types(segment: str) -> list[str]:
    if "seg-" not in segment:
        return []
    body_types = []
    for part in segment.split("--"):
        if part.startswith("seg-"):
            body_types.append(part[len("seg-") :])
    return body_types


def _parse_filters_from_url(url: str) -> tuple[list[dict[str, str]], str, int, set[str]]:
    parsed = urlparse(url)
    query_params = parse_qsl(parsed.query, keep_blank_values=True)
    filters: list[dict[str, str]] = []
    sort_by = DEFAULT_SORT_BY
    start_page = 1
    inferred_names: set[str] = set()

    seen_pairs: set[tuple[str, str]] = set()
    seen_names: set[str] = set()

    def add_filter(name: str, value: str) -> None:
        if not name or value == "":
            return
        pair = (name, value)
        if pair in seen_pairs:
            return
        seen_pairs.add(pair)
        seen_names.add(name)
        filters.append({"name": name, "value": value})

    for key, value in query_params:
        if key == "page" and value:
            try:
                start_page = int(value)
            except ValueError:
                pass
            continue
        if not key.startswith("search["):
            continue
        name = key[len("search[") :]
        if name.endswith("]"):
            name = name[:-1]
        if "][" in name:
            name = name.split("][", 1)[0]
        if name == "order" and value:
            sort_by = value
            continue
        if name == "page" and value:
            try:
                start_page = int(value)
            except ValueError:
                pass
            continue
        add_filter(name, value)

    segments = [seg for seg in parsed.path.split("/") if seg]
    category_slug = segments[0] if segments else None
    if category_slug and "category_id" not in seen_names:
        category_id = CATEGORY_SLUG_TO_ID.get(category_slug)
        if category_id:
            add_filter("category_id", category_id)

    remaining: list[str] = []
    for segment in segments[1:]:
        body_types = _segment_body_types(segment)
        if body_types:
            for body_type in body_types:
                add_filter("filter_enum_body_type", body_type)
            continue
        if segment.startswith("od-"):
            year_from = segment[len("od-") :]
            if "filter_float_year:from" not in seen_names:
                add_filter("filter_float_year:from", year_from)
            continue
        if segment.startswith("do-"):
            year_to = segment[len("do-") :]
            if "filter_float_year:to" not in seen_names:
                add_filter("filter_float_year:to", year_to)
            continue
        region_id = REGION_SLUG_TO_ID.get(segment)
        if region_id:
            if "region_id" not in seen_names:
                add_filter("region_id", region_id)
            continue
        remaining.append(segment)

    if remaining:
        if "filter_enum_make" not in seen_names:
            add_filter("filter_enum_make", remaining[0])
            inferred_names.add("filter_enum_make")
        if len(remaining) > 1 and "filter_enum_model" not in seen_names:
            add_filter("filter_enum_model", remaining[1])
            inferred_names.add("filter_enum_model")

    return filters, sort_by, start_page, inferred_names


def _build_payload(filters: list[dict[str, str]], sort_by: str, page: int) -> dict:
    return {
        "extensions": {
            "persistedQuery": {
                "sha256Hash": PERSISTED_QUERY_HASH,
                "version": 1,
            }
        },
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


def _post_graphql(payload: dict, headers: dict[str, str], timeout_s: float) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = Request(GRAPHQL_ENDPOINT, data=body, headers=headers, method="POST")
    with urlopen(request, timeout=timeout_s) as response:
        data = response.read()
    parsed = json.loads(data.decode("utf-8"))
    if "errors" in parsed:
        raise RuntimeError(f"GraphQL errors: {parsed['errors']}")
    return parsed


def _iter_embedded_json_values(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _iter_embedded_json_values(nested)
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_embedded_json_values(item)
        return
    if isinstance(value, str) and value[:1] in {"{", "["}:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return
        yield from _iter_embedded_json_values(parsed)


def _extract_canonical_filter_mappings(html: str, target_names: set[str]) -> dict[tuple[str, str], str]:
    next_data_match = re.search(
        r'<script\b(?=[^>]*\bid=["\']__NEXT_DATA__["\'])(?=[^>]*\btype=["\']application/json["\'])[^>]*>(?P<body>.*?)</script>',
        html,
        re.DOTALL,
    )
    if not next_data_match:
        return {}
    try:
        next_data = json.loads(next_data_match.group("body"))
    except json.JSONDecodeError:
        return {}

    mappings: dict[tuple[str, str], str] = {}
    for item in _iter_embedded_json_values(next_data):
        name = item.get("name")
        value = item.get("value")
        canonical = item.get("canonical")
        if name not in target_names:
            continue
        if not isinstance(value, str) or not isinstance(canonical, str):
            continue
        mappings[(name, canonical)] = value
    return mappings


def _extract_search_page_total_count(html: str) -> int | None:
    next_data_match = re.search(
        r'<script\b(?=[^>]*\bid=["\']__NEXT_DATA__["\'])(?=[^>]*\btype=["\']application/json["\'])[^>]*>(?P<body>.*?)</script>',
        html,
        re.DOTALL,
    )
    if not next_data_match:
        return None
    try:
        next_data = json.loads(next_data_match.group("body"))
    except json.JSONDecodeError:
        return None

    for item in _iter_embedded_json_values(next_data):
        if "advertSearch" in item and isinstance(item["advertSearch"], dict):
            total_count = item["advertSearch"].get("totalCount")
            if isinstance(total_count, int):
                return total_count
        if "appliedFilters" in item and "totalCount" in item:
            total_count = item.get("totalCount")
            if isinstance(total_count, int):
                return total_count
    return None


def _item_key_from_node(node: dict) -> tuple[str, str | None]:
    item_id = node.get("id")
    if isinstance(item_id, str) and item_id:
        return f"id:{item_id}", item_id
    payload = json.dumps(node, sort_keys=True, ensure_ascii=True)
    return f"hash:{hashlib.sha1(payload.encode('utf-8')).hexdigest()}", None


def _item_key_from_html(html: str) -> str:
    return f"hash:{hashlib.sha1(html.encode('utf-8')).hexdigest()}"


def _load_existing_item_keys(output_path: Path) -> set[str]:
    if not output_path.exists():
        return set()
    keys: set[str] = set()
    with output_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            item_key = record.get("item_key")
            if isinstance(item_key, str):
                keys.add(item_key)
                continue
            item_id = record.get("item_id")
            if isinstance(item_id, str):
                keys.add(f"id:{item_id}")
                continue
            html = record.get("html")
            if isinstance(html, str):
                keys.add(_item_key_from_html(html))
    return keys


def _append_results(
    output_path: Path,
    page_url: str,
    page_number: int,
    edges: Iterable[dict],
    *,
    seen_item_keys: set[str],
    search_url: str,
) -> tuple[int, int]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0
    with output_path.open("a", encoding="utf-8") as handle:
        for item_index, edge in enumerate(edges):
            node = edge.get("node") if isinstance(edge, dict) else None
            node = node if isinstance(node, dict) else {}
            item_key, item_id = _item_key_from_node(node)
            if item_key in seen_item_keys:
                skipped += 1
                continue
            seen_item_keys.add(item_key)
            record = {
                "search_url": search_url,
                "page_url": page_url,
                "page_number": page_number,
                "item_index": item_index,
                "item_id": item_id,
                "item_key": item_key,
                "node": node,
                "edge": edge,
            }
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
            written += 1
    return written, skipped


RequestFunc = Callable[[dict, dict[str, str], float], dict]
PageRequestFunc = Callable[[str, dict[str, str], float], str]


def _emit_progress(callback: ProgressCallback | None, event: str, **payload: Any) -> None:
    if callback is None:
        return
    callback({"event": event, **payload})


def _fetch_page_text(url: str, headers: dict[str, str], timeout_s: float) -> str:
    request = Request(url, headers=headers, method="GET")
    with urlopen(request, timeout=timeout_s) as response:
        return response.read().decode("utf-8")


def _resolve_canonical_make_model_filters(
    url: str,
    filters: list[dict[str, str]],
    *,
    headers: dict[str, str],
    timeout_s: float,
    page_request_func: PageRequestFunc | None = None,
    retry_attempts: int = 1,
    backoff_base: float = 0.0,
) -> tuple[list[dict[str, str]], bool, int | None]:
    make_index: int | None = None
    model_index: int | None = None
    for index, item in enumerate(filters):
        name = item.get("name")
        if name == "filter_enum_make" and make_index is None:
            make_index = index
        elif name == "filter_enum_model" and model_index is None:
            model_index = index

    if make_index is None and model_index is None:
        return filters, False, None

    page_request = page_request_func or _fetch_page_text
    try:
        html = _with_retry(
            lambda: page_request(_url_with_page(_normalize_start_url(url), 1), headers, timeout_s),
            attempts=max(1, retry_attempts),
            base_delay=backoff_base,
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
    target_names = {"filter_enum_make", "filter_enum_model"}
    mappings = _extract_canonical_filter_mappings(html, target_names)
    page_total_count = _extract_search_page_total_count(html)
    resolved_filters = [dict(item) for item in filters]
    matched_names: set[str] = set()
    for index in (make_index, model_index):
        if index is None:
            continue
        item = resolved_filters[index]
        resolved_value = mappings.get((item["name"], item["value"]))
        if resolved_value:
            matched_names.add(item["name"])
            item["value"] = resolved_value
    return resolved_filters, False, page_total_count


def parse_pages(
    start_url: str,
    output_path: Path,
    state_path: Path,
    *,
    run_mode: str = RUN_MODE_RESUME,
    max_pages: int | None = None,
    retry_attempts: int = 4,
    backoff_base: float = 1.0,
    delay_min: float = 10.0,
    delay_max: float = 20.0,
    request_timeout_s: float = 45.0,
    user_agent: str | None = DEFAULT_USER_AGENT,
    accept_language: str | None = DEFAULT_ACCEPT_LANGUAGE,
    request_func: RequestFunc | None = None,
    page_request_func: PageRequestFunc | None = None,
    progress_callback: ProgressCallback | None = None,
) -> ParserState:
    if run_mode not in RUN_MODES:
        raise ValueError(f"Unknown run mode '{run_mode}'. Expected one of {sorted(RUN_MODES)}.")
    normalized_start_url = _normalize_start_url(start_url)
    if run_mode == RUN_MODE_FULL:
        if output_path.exists():
            output_path.unlink()
        if state_path.exists():
            state_path.unlink()

    state = _read_state(state_path) if run_mode == RUN_MODE_RESUME else None
    if state and _normalize_start_url(state.start_url) != normalized_start_url:
        LOGGER.info("Existing state URL does not match the requested URL. Starting fresh.")
        state = None

    filters, sort_by, start_page, _ = _parse_filters_from_url(start_url)
    if state and not state.has_more:
        LOGGER.info("State indicates no more pages to fetch. Exiting.")
        _emit_progress(progress_callback, "complete", state=asdict(state), next_url=state.next_url)
        return state

    current_page = state.next_page if state else start_page
    pages_completed = state.pages_completed if state else 0
    results_written = state.results_written if state else 0

    _emit_progress(
        progress_callback,
        "start",
        start_url=normalized_start_url,
        state={
            "start_url": normalized_start_url,
            "next_page": current_page,
            "pages_completed": pages_completed,
            "results_written": results_written,
            "has_more": True,
        },
    )

    seen_item_keys = set()
    if run_mode != RUN_MODE_FULL:
        seen_item_keys = _load_existing_item_keys(output_path)
        if seen_item_keys:
            LOGGER.info("Loaded %s existing items for deduplication.", len(seen_item_keys))

    custom_request_func = request_func is not None
    request_func = request_func or _post_graphql
    headers = {
        "accept": "application/graphql-response+json, application/graphql+json, application/json, text/event-stream, multipart/mixed",
        "content-type": "application/json",
        "sitecode": "otomotopl",
    }
    if user_agent:
        headers["User-Agent"] = user_agent
    if accept_language:
        headers["accept-language"] = accept_language
    page_total_count: int | None = None
    if page_request_func is not None or not custom_request_func:
        filters, _, page_total_count = _resolve_canonical_make_model_filters(
            start_url,
            filters,
            headers=headers,
            timeout_s=request_timeout_s,
            page_request_func=page_request_func,
            retry_attempts=retry_attempts,
            backoff_base=backoff_base,
        )

    has_more = True
    next_page = current_page
    while True:
        if max_pages is not None and pages_completed >= max_pages:
            LOGGER.info("Reached max pages limit (%s).", max_pages)
            break

        _emit_progress(
            progress_callback,
            "page_fetch_started",
            page=current_page,
            pages_completed=pages_completed,
            results_written=results_written,
        )
        payload = _build_payload(filters, sort_by, current_page)

        def fetch_page() -> dict:
            return request_func(payload, headers, request_timeout_s)

        response = _with_retry(
            fetch_page,
            attempts=retry_attempts,
            base_delay=backoff_base,
            label="graphql fetch",
            logger=LOGGER,
        )

        data = response.get("data") if isinstance(response, dict) else None
        advert_search = data.get("advertSearch") if isinstance(data, dict) else None
        if not isinstance(advert_search, dict):
            raise RuntimeError("GraphQL response missing advertSearch data")
        edges = advert_search.get("edges", [])
        if not isinstance(edges, list):
            raise RuntimeError("GraphQL response edges is not a list")
        total_count = advert_search.get("totalCount")
        if current_page == 1 and not edges and total_count == 0 and isinstance(page_total_count, int) and page_total_count > 0:
            raise RuntimeError(
                "GraphQL returned 0 listings even though the search page reports results. Canonical filter resolution failed."
            )

        page_url = _url_with_page(normalized_start_url, current_page)
        LOGGER.info("Fetched page %s with %s edges.", current_page, len(edges))

        written, skipped = _append_results(
            output_path,
            page_url,
            current_page,
            edges,
            seen_item_keys=seen_item_keys,
            search_url=normalized_start_url,
        )
        results_written += written
        pages_completed += 1
        LOGGER.info(
            "Appended %s results (skipped %s). Total pages=%s total results=%s.",
            written,
            skipped,
            pages_completed,
            results_written,
        )
        current_state = ParserState(
            start_url=normalized_start_url,
            next_page=current_page + 1,
            pages_completed=pages_completed,
            results_written=results_written,
            has_more=True,
        )
        _emit_progress(
            progress_callback,
            "page_fetch_finished",
            page=current_page,
            page_url=page_url,
            edges_count=len(edges),
            written=written,
            skipped=skipped,
            state=asdict(current_state),
            next_url=current_state.next_url,
        )
        if run_mode == RUN_MODE_APPEND_NEWER and edges and written == 0:
            LOGGER.info("All listings on this page already exist; stopping append-newer mode.")
            has_more = False
            break

        page_info = advert_search.get("pageInfo") if isinstance(advert_search.get("pageInfo"), dict) else {}
        page_size = page_info.get("pageSize") if isinstance(page_info.get("pageSize"), int) else len(edges)
        current_offset = page_info.get("currentOffset") if isinstance(page_info.get("currentOffset"), int) else (current_page - 1) * page_size

        if not edges:
            has_more = False
        elif isinstance(total_count, int) and total_count >= 0:
            if current_offset + len(edges) >= total_count:
                has_more = False

        next_page = current_page + 1 if has_more else current_page
        _write_state(
            state_path,
            ParserState(
                start_url=normalized_start_url,
                next_page=next_page,
                pages_completed=pages_completed,
                results_written=results_written,
                has_more=has_more,
            ),
        )

        if not has_more:
            LOGGER.info("No more pages to fetch. Stopping.")
            break

        current_page = next_page
        if delay_max > 0:
            wait_time = random.uniform(delay_min, delay_max)
            LOGGER.info("Waiting %.2fs before fetching next page.", wait_time)
            time.sleep(wait_time)

    final_state = ParserState(
        start_url=normalized_start_url,
        next_page=next_page,
        pages_completed=pages_completed,
        results_written=results_written,
        has_more=has_more,
    )
    _write_state(state_path, final_state)
    _emit_progress(progress_callback, "complete", state=asdict(final_state), next_url=final_state.next_url)
    return final_state


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Paginated parser for search results")
    parser.add_argument(
        "url",
        nargs="?",
        help="Start URL to parse (leave empty to be prompted)",
    )
    parser.add_argument(
        "--mode",
        choices=sorted(RUN_MODES),
        default=None,
        help=(
            "Run mode: resume continues from last run, "
            "append-newer starts at page 1 and stops on duplicates, "
            "full overwrites existing output."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="runs",
        help="Base directory to store per-link outputs (ignored when --output/--state are set).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to JSONL output file (overrides --output-dir layout)",
    )
    parser.add_argument(
        "--state",
        default=None,
        help="Path to state file for resuming (overrides --output-dir layout)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum pages to process (testing or partial runs)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=4,
        help="Retry attempts for GraphQL requests",
    )
    parser.add_argument(
        "--backoff",
        type=float,
        default=1.0,
        help="Base backoff delay in seconds",
    )
    parser.add_argument(
        "--delay-min",
        type=float,
        default=10.0,
        help="Minimum delay in seconds before fetching the next page",
    )
    parser.add_argument(
        "--delay-max",
        type=float,
        default=20.0,
        help="Maximum delay in seconds before fetching the next page",
    )
    parser.add_argument(
        "--request-timeout-s",
        type=float,
        default=45.0,
        help="Timeout in seconds for GraphQL requests",
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="User-Agent header for requests",
    )
    parser.add_argument(
        "--accept-language",
        default=DEFAULT_ACCEPT_LANGUAGE,
        help="Accept-Language header for requests",
    )
    parser.add_argument(
        "--aggregate",
        dest="aggregate",
        action="store_true",
        default=True,
        help="Generate aggregations sheet after parsing (default)",
    )
    parser.add_argument(
        "--no-aggregate",
        dest="aggregate",
        action="store_false",
        help="Skip generating the aggregations sheet",
    )
    parser.add_argument(
        "--aggregation-output",
        default=None,
        help="Optional output path for aggregations xlsx",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )

    url = args.url or input("Enter start URL: ").strip()
    if not url:
        raise SystemExit("URL is required.")

    mode = args.mode
    if mode is None:
        prompt = "Run mode [resume/append-newer/full] (default resume): "
        mode_input = input(prompt).strip()
        mode = mode_input or RUN_MODE_RESUME
    if mode not in RUN_MODES:
        raise SystemExit(f"Unknown run mode '{mode}'. Expected one of {sorted(RUN_MODES)}.")

    if args.output or args.state:
        output_path = Path(args.output) if args.output else Path(args.state).parent / "results.jsonl"
        state_path = Path(args.state) if args.state else output_path.parent / "state.json"
    else:
        _run_dir, output_path, state_path = build_run_paths(url, args.output_dir)

    state = parse_pages(
        url,
        output_path,
        state_path,
        run_mode=mode,
        max_pages=args.max_pages,
        retry_attempts=args.retries,
        backoff_base=args.backoff,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        request_timeout_s=args.request_timeout_s,
        user_agent=args.user_agent,
        accept_language=args.accept_language,
    )
    if args.aggregate and output_path.exists() and output_path.stat().st_size > 0:
        from .aggregation import generate_aggregations

        aggregation_path = Path(args.aggregation_output) if args.aggregation_output else None
        generate_aggregations(output_path, aggregation_path)
    print(
        json.dumps(
            {
                "pages_completed": state.pages_completed,
                "results_written": state.results_written,
                "next_url": state.next_url,
                "has_more": state.has_more,
            },
            indent=2,
        )
    )


__all__ = ["build_arg_parser", "build_run_paths", "main", "parse_pages"]
