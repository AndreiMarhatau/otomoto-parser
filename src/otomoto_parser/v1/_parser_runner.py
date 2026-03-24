from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from ._parser_common import (
    LOGGER,
    ProgressCallback,
    RUN_MODE_FULL,
    RUN_MODE_RESUME,
    RUN_MODES,
    ParserRunOptions,
    ParserState,
    _emit_progress,
    _normalize_start_url,
)
from ._parser_cli import build_arg_parser, main as cli_main
from ._parser_filters import _parse_filters_from_url
from ._parser_html import _post_graphql, _resolve_canonical_make_model_filters
from ._parser_retry import RetryPolicy
from ._parser_runtime import _run_pages
from ._parser_storage import _load_existing_item_keys, _read_state


def parse_pages(
    start_url: str,
    *path_args: Path,
    options: ParserRunOptions | None = None,
    **legacy_kwargs: Any,
) -> ParserState:
    output_path, state_path = _resolve_run_paths(path_args)
    resolved_options = _resolve_run_options(options, legacy_kwargs)
    normalized_start_url, state = _prepare_run(start_url, output_path, state_path, resolved_options.run_mode)
    filters, sort_by, start_page, inferred_names = _parse_filters_from_url(start_url)
    if state and not state.has_more:
        LOGGER.info("State indicates no more pages to fetch. Exiting.")
        _emit_progress(resolved_options.progress_callback, "complete", state=asdict(state), next_url=state.next_url)
        return state

    context = _build_runtime_context(
        normalized_start_url,
        output_path,
        {"state": state, "start_page": start_page, "run_mode": resolved_options.run_mode},
        {
            "user_agent": resolved_options.user_agent,
            "accept_language": resolved_options.accept_language,
            "request_func": resolved_options.request_func,
        },
    )
    filters, page_total_count = _resolve_filters_if_needed(
        start_url,
        filters,
        inferred_names,
        {
            "page_request_func": resolved_options.page_request_func,
            "retry_policy": RetryPolicy(attempts=resolved_options.retry_attempts, base_delay=resolved_options.backoff_base),
            "timeout_s": resolved_options.request_timeout_s,
            "headers": context["headers"],
            "custom_request_func": context["custom_request_func"],
        },
    )
    _emit_start(resolved_options.progress_callback, normalized_start_url, context)
    return _run_pages(
        {
            "filters": filters,
            "sort_by": sort_by,
            "page_total_count": page_total_count,
            "output_path": output_path,
            "state_path": state_path,
            "progress_callback": resolved_options.progress_callback,
            "max_pages": resolved_options.max_pages,
            "retry_policy": RetryPolicy(attempts=resolved_options.retry_attempts, base_delay=resolved_options.backoff_base),
            "delay_min": resolved_options.delay_min,
            "delay_max": resolved_options.delay_max,
            "request_timeout_s": resolved_options.request_timeout_s,
            "run_mode": resolved_options.run_mode,
        },
        context,
    )


def _resolve_run_paths(path_args: tuple[Path, ...]) -> tuple[Path, Path]:
    if len(path_args) != 2:
        raise TypeError("parse_pages expects output_path and state_path after start_url.")
    output_path, state_path = path_args
    return Path(output_path), Path(state_path)


def _resolve_run_options(
    options: ParserRunOptions | None,
    legacy_kwargs: dict[str, Any],
) -> ParserRunOptions:
    if options is None:
        return ParserRunOptions(**legacy_kwargs)
    if legacy_kwargs:
        raise TypeError("parse_pages accepts either options or legacy keyword arguments, not both.")
    return options


def _prepare_run(start_url: str, output_path: Path, state_path: Path, run_mode: str) -> tuple[str, ParserState | None]:
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
    return normalized_start_url, state


def _build_runtime_context(
    normalized_start_url: str,
    output_path: Path,
    run_state: dict[str, Any],
    request_settings: dict[str, Any],
) -> dict[str, Any]:
    headers = {
        "accept": "application/graphql-response+json, application/graphql+json, application/json, text/event-stream, multipart/mixed",
        "content-type": "application/json",
        "sitecode": "otomotopl",
    }
    if request_settings.get("user_agent"):
        headers["User-Agent"] = request_settings["user_agent"]
    if request_settings.get("accept_language"):
        headers["accept-language"] = request_settings["accept_language"]
    seen_item_keys = set() if run_state["run_mode"] == RUN_MODE_FULL else _load_existing_item_keys(output_path)
    if seen_item_keys:
        LOGGER.info("Loaded %s existing items for deduplication.", len(seen_item_keys))
    state = run_state["state"]
    return {
        "normalized_start_url": normalized_start_url,
        "current_page": state.next_page if state else run_state["start_page"],
        "pages_completed": state.pages_completed if state else 0,
        "results_written": state.results_written if state else 0,
        "headers": headers,
        "request_func": request_settings.get("request_func") or _post_graphql,
        "custom_request_func": request_settings.get("request_func") is not None,
        "seen_item_keys": seen_item_keys,
    }


def _resolve_filters_if_needed(start_url: str, filters: list[dict[str, str]], inferred_names: set[str], resolution: dict[str, Any]) -> tuple[list[dict[str, str]], int | None]:
    page_total_count: int | None = None
    if resolution.get("page_request_func") is not None or not resolution["custom_request_func"]:
        filters, _, page_total_count = _resolve_canonical_make_model_filters(
            start_url,
            filters,
            inferred_names,
            {
                "headers": resolution["headers"],
                "timeout_s": resolution["timeout_s"],
                "page_request_func": resolution.get("page_request_func"),
                "retry_attempts": resolution["retry_policy"].attempts,
                "backoff_base": resolution["retry_policy"].base_delay,
            },
        )
    return filters, page_total_count


def _emit_start(progress_callback: ProgressCallback | None, normalized_start_url: str, context: dict[str, Any]) -> None:
    _emit_progress(
        progress_callback,
        "start",
        start_url=normalized_start_url,
        state={
            "start_url": normalized_start_url,
            "next_page": context["current_page"],
            "pages_completed": context["pages_completed"],
            "results_written": context["results_written"],
            "has_more": True,
        },
    )

def main() -> None:
    cli_main(parse_pages)


__all__ = ["build_arg_parser", "main", "parse_pages"]
