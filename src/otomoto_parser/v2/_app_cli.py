from __future__ import annotations

import argparse
from pathlib import Path


def frontend_dist_dir(base_file: str) -> Path:
    return Path(base_file).resolve().parent / "frontend" / "dist"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Otomoto parser UI application.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", default=".parser-app-data")
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--backoff", type=float, default=1.0)
    parser.add_argument("--delay-min", type=float, default=0.0)
    parser.add_argument("--delay-max", type=float, default=0.0)
    parser.add_argument("--request-timeout-s", type=float, default=45.0)
    return parser


def parser_options_from_args(args) -> dict[str, float | int]:
    return {
        "retry_attempts": args.retries,
        "backoff_base": args.backoff,
        "delay_min": args.delay_min,
        "delay_max": args.delay_max,
        "request_timeout_s": args.request_timeout_s,
    }
