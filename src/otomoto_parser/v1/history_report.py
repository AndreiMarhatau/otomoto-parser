from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from ._history_client import VehicleHistoryClient
from ._history_common import (
    DEFAULT_ACCEPT_LANGUAGE,
    DEFAULT_BACKOFF_BASE_S,
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_TIMEOUT_S,
    DEFAULT_USER_AGENT,
    CancellationRequested,
    OpenerLike,
    RetrySettings,
    VehicleHistoryClientConfig,
    VehicleHistoryBootstrap,
    VehicleHistoryRequestOptions,
    VehicleHistoryReport,
    _extract_api_version,
    _normalize_first_registration_date,
    _normalize_registration_number,
    _normalize_vin_number,
    _with_retry,
)


def fetch_vehicle_history(
    *request_args: str | date | datetime,
    options: VehicleHistoryRequestOptions | None = None,
    **legacy_kwargs: object,
) -> VehicleHistoryReport:
    if len(request_args) != 3:
        raise TypeError("fetch_vehicle_history expects registration number, VIN number, and first registration date.")
    resolved_options = _resolve_history_request_options(options, legacy_kwargs)
    client = VehicleHistoryClient(
        VehicleHistoryClientConfig(
            user_agent=resolved_options.user_agent,
            accept_language=resolved_options.accept_language,
            timeout_s=resolved_options.timeout_s,
            retry_attempts=resolved_options.retry_attempts,
            backoff_base_s=resolved_options.backoff_base_s,
        )
    )
    return client.fetch_report(
        str(request_args[0]),
        str(request_args[1]),
        request_args[2],
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Historia Pojazdu reports.")
    parser.add_argument("registration_number", help="Vehicle registration number")
    parser.add_argument("vin_number", help="VIN number")
    parser.add_argument("first_registration_date", help="First registration date: YYYY-MM-DD")
    parser.add_argument("--timeout-s", type=float, default=DEFAULT_TIMEOUT_S, help="HTTP timeout in seconds")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRY_ATTEMPTS, help="Retry attempts")
    parser.add_argument("--backoff", type=float, default=DEFAULT_BACKOFF_BASE_S, help="Exponential backoff base delay")
    parser.add_argument("--output", default=None, help="Optional path to write the JSON result")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = fetch_vehicle_history(
        args.registration_number,
        args.vin_number,
        args.first_registration_date,
        timeout_s=args.timeout_s,
        retry_attempts=args.retries,
        backoff_base_s=args.backoff,
    )
    output = json.dumps(asdict(report), ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


__all__ = [
    "CancellationRequested",
    "DEFAULT_ACCEPT_LANGUAGE",
    "DEFAULT_BACKOFF_BASE_S",
    "DEFAULT_RETRY_ATTEMPTS",
    "DEFAULT_TIMEOUT_S",
    "DEFAULT_USER_AGENT",
    "OpenerLike",
    "RetrySettings",
    "VehicleHistoryClientConfig",
    "VehicleHistoryBootstrap",
    "VehicleHistoryRequestOptions",
    "VehicleHistoryClient",
    "VehicleHistoryReport",
    "_extract_api_version",
    "_normalize_first_registration_date",
    "_normalize_registration_number",
    "_normalize_vin_number",
    "_with_retry",
    "build_arg_parser",
    "fetch_vehicle_history",
    "main",
]


def _resolve_history_request_options(
    options: VehicleHistoryRequestOptions | None,
    legacy_kwargs: dict[str, object],
) -> VehicleHistoryRequestOptions:
    if options is None:
        return VehicleHistoryRequestOptions(**legacy_kwargs)
    if legacy_kwargs:
        raise TypeError("fetch_vehicle_history accepts either options or legacy keyword arguments, not both.")
    return options
