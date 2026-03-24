from __future__ import annotations

import argparse
import http.client
import json
import logging
import re
import threading
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

LOGGER = logging.getLogger("otomoto_parser.history_report")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/26.4 Safari/605.1.15"
)
DEFAULT_ACCEPT_LANGUAGE = "en-US,en;q=0.9"
DEFAULT_TIMEOUT_S = 45.0
DEFAULT_RETRY_ATTEMPTS = 4
DEFAULT_BACKOFF_BASE_S = 1.0

INIT_URL = "https://moj.gov.pl/nforms/engine/ng/index?xFormsAppName=HistoriaPojazdu#/search"
API_VERSION_PATTERN = '/nforms/api/HistoriaPojazdu/'
DATA_ENDPOINTS = ("vehicle-data", "autodna-data", "carfax-data", "timeline-data")
API_VERSION_REGEX = re.compile(r"/nforms/api/HistoriaPojazdu/([^/\"'?]+)(?:/resource|[/?\"'])")


class OpenerLike(Protocol):
    def open(self, request: Request, timeout: float = ...) -> Any: ...


@dataclass
class VehicleHistoryReport:
    registration_number: str
    vin_number: str
    first_registration_date: str
    api_version: str
    technical_data: dict[str, Any]
    autodna_data: dict[str, Any]
    carfax_data: dict[str, Any]
    timeline_data: dict[str, Any]


class CancellationRequested(RuntimeError):
    pass


def _normalize_first_registration_date(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        raise ValueError("Unsupported first registration date format. Use YYYY-MM-DD.")
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise ValueError("Unsupported first registration date format. Use YYYY-MM-DD.") from exc


def _normalize_registration_number(value: str) -> str:
    normalized = "".join(value.upper().split())
    if not normalized:
        raise ValueError("Registration number cannot be empty.")
    return normalized


def _normalize_vin_number(value: str) -> str:
    normalized = "".join(value.upper().split())
    if not normalized:
        raise ValueError("VIN number cannot be empty.")
    return normalized


def _extract_api_version(html: str) -> str:
    match = API_VERSION_REGEX.search(html)
    if match is not None:
        return match.group(1)
    marker_index = html.find(API_VERSION_PATTERN)
    if marker_index == -1:
        raise RuntimeError("Could not determine HistoriaPojazdu API version from bootstrap HTML.")
    start = marker_index + len(API_VERSION_PATTERN)
    end_candidates = [
        candidate
        for candidate in (html.find("/resource", start), html.find("?", start), html.find('"', start), html.find("'", start))
        if candidate != -1
    ]
    if not end_candidates:
        raise RuntimeError("Could not determine HistoriaPojazdu API version from bootstrap HTML.")
    return html[start : min(end_candidates)]


def _raise_for_status(error: HTTPError) -> None:
    if 400 <= error.code < 500:
        raise error
    raise error


def _error_detail(error: HTTPError) -> str:
    detail = error.reason or "Unexpected upstream error."
    if error.fp is None:
        return str(detail)
    try:
        body = error.fp.read().decode("utf-8", "replace").strip()
    except Exception:  # noqa: BLE001
        return str(detail)
    return body or str(detail)


def _with_retry(
    action,
    *,
    attempts: int,
    base_delay: float,
    label: str,
    should_abort=None,
) -> Any:
    total_attempts = max(0, attempts) + 1
    last_error: Exception | None = None

    def abort_if_requested() -> None:
        if should_abort is not None and should_abort():
            raise CancellationRequested(f"{label} cancelled.")

    for attempt in range(total_attempts):
        abort_if_requested()
        try:
            return action()
        except HTTPError as exc:
            last_error = exc
            if 400 <= exc.code < 500 or attempt == total_attempts - 1:
                raise
        except (URLError, TimeoutError, ConnectionResetError, http.client.RemoteDisconnected) as exc:
            last_error = exc
            if attempt == total_attempts - 1:
                raise
        delay = base_delay * (2**attempt)
        LOGGER.warning(
            "Retrying %s after error (%s: %s). Attempt %s/%s in %.2fs.",
            label,
            last_error.__class__.__name__,
            str(last_error),
            attempt + 1,
            total_attempts - 1,
            delay,
        )
        slept = 0.0
        while slept < delay:
            abort_if_requested()
            remaining = min(0.1, delay - slept)
            time.sleep(remaining)
            slept += remaining
    if last_error:
        raise last_error
    raise RuntimeError(f"{label} failed without raising an exception")


class VehicleHistoryClient:
    def __init__(
        self,
        *,
        opener: OpenerLike | None = None,
        cookie_jar: CookieJar | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        accept_language: str = DEFAULT_ACCEPT_LANGUAGE,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        backoff_base_s: float = DEFAULT_BACKOFF_BASE_S,
        cancel_event: threading.Event | None = None,
    ) -> None:
        discovered_cookie_jar = cookie_jar
        if discovered_cookie_jar is None and opener is not None:
            handlers = getattr(opener, "handlers", [])
            for handler in handlers:
                if isinstance(handler, HTTPCookieProcessor):
                    discovered_cookie_jar = handler.cookiejar
                    break
        self.cookie_jar = discovered_cookie_jar if discovered_cookie_jar is not None else CookieJar()
        self.opener = opener if opener is not None else build_opener(HTTPCookieProcessor(self.cookie_jar))
        if opener is not None:
            handlers = getattr(self.opener, "handlers", [])
            has_cookie_processor = any(isinstance(handler, HTTPCookieProcessor) for handler in handlers)
            for handler in handlers:
                if isinstance(handler, HTTPCookieProcessor):
                    handler.cookiejar = self.cookie_jar
                    break
            else:
                if hasattr(self.opener, "add_handler"):
                    self.opener.add_handler(HTTPCookieProcessor(self.cookie_jar))
        self.user_agent = user_agent
        self.accept_language = accept_language
        self.timeout_s = timeout_s
        self.retry_attempts = retry_attempts
        self.backoff_base_s = backoff_base_s
        self.cancel_event = cancel_event

    def fetch_report(
        self,
        registration_number: str,
        vin_number: str,
        first_registration_date: str | date | datetime,
    ) -> VehicleHistoryReport:
        normalized_date = _normalize_first_registration_date(first_registration_date)
        normalized_registration_number = _normalize_registration_number(registration_number)
        normalized_vin_number = _normalize_vin_number(vin_number)
        self._raise_if_cancelled()
        nf_wid = f"HistoriaPojazdu:{int(time.time() * 1000)}"
        api_version = self._bootstrap_session(nf_wid)
        xsrf_token = self._cookie_value("XSRF-TOKEN")
        payload = {
            "registrationNumber": normalized_registration_number,
            "VINNumber": normalized_vin_number,
            "firstRegistrationDate": normalized_date,
        }

        responses: dict[str, dict[str, Any]] = {}
        for endpoint in DATA_ENDPOINTS:
            self._raise_if_cancelled()
            try:
                responses[endpoint] = self._post_data(
                    api_version=api_version,
                    endpoint=endpoint,
                    nf_wid=nf_wid,
                    xsrf_token=xsrf_token,
                    payload=payload,
                )
            except HTTPError as exc:
                if endpoint in {"autodna-data", "carfax-data"} and exc.code == 404:
                    responses[endpoint] = {
                        "unavailable": True,
                        "status": exc.code,
                        "message": "This external report is not available for the vehicle.",
                    }
                    continue
                detail = _error_detail(exc)
                raise RuntimeError(f"HistoriaPojazdu {endpoint} failed with HTTP {exc.code}: {detail}") from exc
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"HistoriaPojazdu {endpoint} failed: {exc}") from exc

        return VehicleHistoryReport(
            registration_number=normalized_registration_number,
            vin_number=normalized_vin_number,
            first_registration_date=normalized_date,
            api_version=api_version,
            technical_data=responses["vehicle-data"],
            autodna_data=responses["autodna-data"],
            carfax_data=responses["carfax-data"],
            timeline_data=responses["timeline-data"],
        )

    def _bootstrap_session(self, nf_wid: str) -> str:
        attempts = [
            (
                "HistoriaPojazdu bootstrap shell",
                Request(
                    INIT_URL,
                    method="GET",
                    headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": self.accept_language,
                        "User-Agent": self.user_agent,
                    },
                ),
            ),
            (
                "HistoriaPojazdu bootstrap app",
                Request(
                    INIT_URL,
                    data=urlencode({"NF_WID": nf_wid}).encode("utf-8"),
                    method="POST",
                    headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": self.accept_language,
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Origin": "null",
                        "Referer": INIT_URL,
                        "User-Agent": self.user_agent,
                    },
                ),
            ),
        ]

        last_error: RuntimeError | None = None
        for label, request in attempts:
            def action() -> str:
                self._raise_if_cancelled()
                with self.opener.open(request, timeout=self.timeout_s) as response:
                    return response.read().decode("utf-8")

            try:
                html = _with_retry(
                    action,
                    attempts=self.retry_attempts,
                    base_delay=self.backoff_base_s,
                    label=label,
                    should_abort=self._is_cancelled,
                )
            except CancellationRequested:
                raise
            except (HTTPError, URLError, TimeoutError, ConnectionResetError, http.client.RemoteDisconnected) as exc:
                last_error = RuntimeError(f"{label} failed: {exc}")
                LOGGER.info("%s failed during bootstrap transport; trying next bootstrap strategy.", label)
                continue
            try:
                api_version = _extract_api_version(html)
            except RuntimeError as exc:
                last_error = exc
                LOGGER.info("%s did not expose the HistoriaPojazdu API version; trying next bootstrap strategy.", label)
                continue
            if not self._has_cookie("XSRF-TOKEN"):
                last_error = RuntimeError(f"{label} did not establish the required HistoriaPojazdu session cookies.")
                LOGGER.info("%s exposed an API version but did not provide XSRF session cookies; trying next bootstrap strategy.", label)
                continue
            return api_version
        if last_error is not None:
            raise last_error
        raise RuntimeError("Could not determine HistoriaPojazdu API version from bootstrap HTML.")

    def _post_data(
        self,
        *,
        api_version: str,
        endpoint: str,
        nf_wid: str,
        xsrf_token: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        request = Request(
            f"https://moj.gov.pl/nforms/api/HistoriaPojazdu/{api_version}/data/{endpoint}",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Accept": "application/json",
                "Accept-Language": self.accept_language,
                "Content-Type": "application/json",
                "NF_WID": nf_wid,
                "Origin": "https://moj.gov.pl",
                "User-Agent": self.user_agent,
                "X-XSRF-TOKEN": xsrf_token,
            },
        )

        def action() -> dict[str, Any]:
            self._raise_if_cancelled()
            with self.opener.open(request, timeout=self.timeout_s) as response:
                return json.loads(response.read().decode("utf-8"))

        return _with_retry(
            action,
            attempts=self.retry_attempts,
            base_delay=self.backoff_base_s,
            label=f"HistoriaPojazdu {endpoint}",
            should_abort=self._is_cancelled,
        )

    def _cookie_value(self, name: str) -> str:
        for cookie in self.cookie_jar:
            if cookie.name == name:
                return cookie.value
        raise RuntimeError(f"Missing required cookie: {name}")

    def _has_cookie(self, name: str) -> bool:
        for cookie in self.cookie_jar:
            if cookie.name == name and cookie.value:
                return True
        return False

    def _is_cancelled(self) -> bool:
        return self.cancel_event.is_set() if self.cancel_event is not None else False

    def _raise_if_cancelled(self) -> None:
        if self._is_cancelled():
            raise CancellationRequested("HistoriaPojazdu request cancelled.")


def fetch_vehicle_history(
    registration_number: str,
    vin_number: str,
    first_registration_date: str | date | datetime,
    *,
    user_agent: str = DEFAULT_USER_AGENT,
    accept_language: str = DEFAULT_ACCEPT_LANGUAGE,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    backoff_base_s: float = DEFAULT_BACKOFF_BASE_S,
) -> VehicleHistoryReport:
    client = VehicleHistoryClient(
        user_agent=user_agent,
        accept_language=accept_language,
        timeout_s=timeout_s,
        retry_attempts=retry_attempts,
        backoff_base_s=backoff_base_s,
    )
    return client.fetch_report(registration_number, vin_number, first_registration_date)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Historia Pojazdu reports.")
    parser.add_argument("registration_number", help="Vehicle registration number")
    parser.add_argument("vin_number", help="VIN number")
    parser.add_argument("first_registration_date", help="First registration date: YYYY-MM-DD")
    parser.add_argument("--timeout-s", type=float, default=DEFAULT_TIMEOUT_S, help="HTTP timeout in seconds")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRY_ATTEMPTS, help="Retry attempts for 5xx/network failures")
    parser.add_argument("--backoff", type=float, default=DEFAULT_BACKOFF_BASE_S, help="Exponential backoff base delay in seconds")
    parser.add_argument("--output", default=None, help="Optional path to write the JSON result")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
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


if __name__ == "__main__":
    raise SystemExit(main())
