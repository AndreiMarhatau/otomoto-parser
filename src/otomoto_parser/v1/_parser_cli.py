from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from ._parser_common import DEFAULT_ACCEPT_LANGUAGE, DEFAULT_USER_AGENT, RUN_MODE_RESUME, RUN_MODES, build_run_paths


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Paginated parser for search results")
    parser.add_argument("url", nargs="?", help="Start URL to parse (leave empty to be prompted)")
    parser.add_argument("--mode", choices=sorted(RUN_MODES), default=None, help="Run mode")
    parser.add_argument("--output-dir", default="runs", help="Base directory to store per-link outputs")
    parser.add_argument("--output", default=None, help="Path to JSONL output file")
    parser.add_argument("--state", default=None, help="Path to state file for resuming")
    parser.add_argument("--max-pages", type=int, default=None, help="Maximum pages to process")
    parser.add_argument("--retries", type=int, default=4, help="Retry attempts for GraphQL requests")
    parser.add_argument("--backoff", type=float, default=1.0, help="Base backoff delay in seconds")
    parser.add_argument("--delay-min", type=float, default=10.0, help="Minimum delay in seconds")
    parser.add_argument("--delay-max", type=float, default=20.0, help="Maximum delay in seconds")
    parser.add_argument("--request-timeout-s", type=float, default=45.0, help="Timeout in seconds for GraphQL requests")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent header for requests")
    parser.add_argument("--accept-language", default=DEFAULT_ACCEPT_LANGUAGE, help="Accept-Language header for requests")
    parser.add_argument("--aggregate", dest="aggregate", action="store_true", default=True, help="Generate aggregations sheet after parsing")
    parser.add_argument("--no-aggregate", dest="aggregate", action="store_false", help="Skip generating the aggregations sheet")
    parser.add_argument("--aggregation-output", default=None, help="Optional output path for aggregations xlsx")
    return parser


def main(parse_pages) -> None:
    args = build_arg_parser().parse_args()
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    url = args.url or input("Enter start URL: ").strip()
    if not url:
        raise SystemExit("URL is required.")
    mode = args.mode or input("Run mode [resume/append-newer/full] (default resume): ").strip() or RUN_MODE_RESUME
    if mode not in RUN_MODES:
        raise SystemExit(f"Unknown run mode '{mode}'. Expected one of {sorted(RUN_MODES)}.")
    output_path, state_path = _resolve_output_paths(url, args.output_dir, args.output, args.state)
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

        generate_aggregations(output_path, Path(args.aggregation_output) if args.aggregation_output else None)
    print(json.dumps({"pages_completed": state.pages_completed, "results_written": state.results_written, "next_url": state.next_url, "has_more": state.has_more}, indent=2))


def _resolve_output_paths(url: str, output_dir: str, output: str | None, state: str | None) -> tuple[Path, Path]:
    if output or state:
        output_path = Path(output) if output else Path(state).parent / "results.jsonl"
        return output_path, Path(state) if state else output_path.parent / "state.json"
    _, output_path, state_path = build_run_paths(url, output_dir)
    return output_path, state_path
