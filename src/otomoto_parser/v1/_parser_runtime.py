from __future__ import annotations

import random
import time
from dataclasses import asdict
from typing import Any

from ._parser_common import LOGGER, RUN_MODE_APPEND_NEWER, ParserState, ProgressCallback, _emit_progress, _url_with_page
from ._parser_filters import _build_payload
from ._parser_retry import RetryPolicy, _with_retry
from ._parser_storage import _append_results, _write_state


def _run_pages(job: dict[str, Any], context: dict[str, Any]) -> ParserState:
    has_more = True
    next_page = context["current_page"]
    while True:
        if job["max_pages"] is not None and context["pages_completed"] >= job["max_pages"]:
            LOGGER.info("Reached max pages limit (%s).", job["max_pages"])
            break
        page_result = _process_page(job, context)
        has_more = page_result["has_more"]
        next_page = page_result["next_page"]
        _write_state(job["state_path"], _state_from_context(context, has_more, next_page))
        if not has_more:
            LOGGER.info("No more pages to fetch. Stopping.")
            break
        context["current_page"] = next_page
        if job["delay_max"] > 0:
            wait_time = random.uniform(job["delay_min"], job["delay_max"])
            LOGGER.info("Waiting %.2fs before fetching next page.", wait_time)
            time.sleep(wait_time)
    final_state = _state_from_context(context, has_more, next_page)
    _write_state(job["state_path"], final_state)
    _emit_progress(job["progress_callback"], "complete", state=asdict(final_state), next_url=final_state.next_url)
    return final_state


def _process_page(job: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    current_page = context["current_page"]
    _emit_progress(job["progress_callback"], "page_fetch_started", page=current_page, pages_completed=context["pages_completed"], results_written=context["results_written"])
    advert_search = _fetch_advert_search(job, current_page, context)
    edges = advert_search.get("edges", [])
    _check_page_total_count(current_page, edges, advert_search.get("totalCount"), job["page_total_count"])
    page_url = _url_with_page(context["normalized_start_url"], current_page)
    LOGGER.info("Fetched page %s with %s edges.", current_page, len(edges))
    written, skipped = _append_results(
        job["output_path"],
        {"page_url": page_url, "page_number": current_page, "edges": edges, "search_url": context["normalized_start_url"]},
        seen_item_keys=context["seen_item_keys"],
    )
    context["results_written"] += written
    context["pages_completed"] += 1
    _emit_page_finished(job["progress_callback"], {"current_page": current_page, "page_url": page_url, "edges": edges, "written": written, "skipped": skipped}, context)
    if job["run_mode"] == RUN_MODE_APPEND_NEWER and edges and written == 0:
        LOGGER.info("All listings on this page already exist; stopping append-newer mode.")
        return {"has_more": False, "next_page": current_page}
    has_more = _has_more_pages(advert_search, current_page, edges)
    return {"has_more": has_more, "next_page": current_page + 1 if has_more else current_page}


def _fetch_advert_search(job: dict[str, Any], current_page: int, context: dict[str, Any]) -> dict[str, Any]:
    payload = _build_payload(job["filters"], job["sort_by"], current_page)
    response = _with_retry(
        lambda: context["request_func"](payload, context["headers"], job["request_timeout_s"]),
        job["retry_policy"] if isinstance(job["retry_policy"], RetryPolicy) else RetryPolicy(attempts=1, base_delay=0.0),
        label="graphql fetch",
        logger=LOGGER,
    )
    data = response.get("data") if isinstance(response, dict) else None
    advert_search = data.get("advertSearch") if isinstance(data, dict) else None
    if not isinstance(advert_search, dict):
        raise RuntimeError("GraphQL response missing advertSearch data")
    if not isinstance(advert_search.get("edges", []), list):
        raise RuntimeError("GraphQL response edges is not a list")
    return advert_search


def _check_page_total_count(current_page: int, edges: list[dict], total_count: Any, page_total_count: int | None) -> None:
    if current_page == 1 and not edges and total_count == 0 and isinstance(page_total_count, int) and page_total_count > 0:
        raise RuntimeError("GraphQL returned 0 listings even though the search page reports results. Canonical filter resolution failed.")


def _emit_page_finished(progress_callback: ProgressCallback | None, page_result: dict[str, Any], context: dict[str, Any]) -> None:
    current_state = _state_from_context(context, True, page_result["current_page"] + 1)
    _emit_progress(
        progress_callback,
        "page_fetch_finished",
        page=page_result["current_page"],
        page_url=page_result["page_url"],
        edges_count=len(page_result["edges"]),
        written=page_result["written"],
        skipped=page_result["skipped"],
        state=asdict(current_state),
        next_url=current_state.next_url,
    )


def _state_from_context(context: dict[str, Any], has_more: bool, next_page: int) -> ParserState:
    return ParserState(
        start_url=context["normalized_start_url"],
        next_page=next_page,
        pages_completed=context["pages_completed"],
        results_written=context["results_written"],
        has_more=has_more,
    )


def _has_more_pages(advert_search: dict[str, Any], current_page: int, edges: list[dict]) -> bool:
    total_count = advert_search.get("totalCount")
    page_info = advert_search.get("pageInfo") if isinstance(advert_search.get("pageInfo"), dict) else {}
    page_size = page_info.get("pageSize") if isinstance(page_info.get("pageSize"), int) else len(edges)
    current_offset = page_info.get("currentOffset") if isinstance(page_info.get("currentOffset"), int) else (current_page - 1) * page_size
    if not edges:
        return False
    if isinstance(total_count, int) and total_count >= 0:
        return current_offset + len(edges) < total_count
    return True
