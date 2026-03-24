from __future__ import annotations

import http.client
import logging
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Protocol, TypeVar
from urllib.error import HTTPError, URLError
from urllib.request import Request


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
API_VERSION_PATTERN = "/nforms/api/HistoriaPojazdu/"
DATA_ENDPOINTS = ("vehicle-data", "autodna-data", "carfax-data", "timeline-data")
API_VERSION_REGEX = re.compile(r"/nforms/api/HistoriaPojazdu/([^/\"'?]+)(?:/resource|[/?\"'])")

T = TypeVar("T")


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


@dataclass(frozen=True)
class VehicleHistoryBootstrap:
    nf_wid: str
    api_version: str
    xsrf_token: str


class CancellationRequested(RuntimeError):
    pass


@dataclass(frozen=True)
class RetrySettings:
    attempts: int
    base_delay: float
    label: str
    should_abort: Callable[[], bool] | None = None


@dataclass(frozen=True)
class VehicleHistoryClientConfig:
    opener: OpenerLike | None = None
    cookie_jar: Any | None = None
    user_agent: str = DEFAULT_USER_AGENT
    accept_language: str = DEFAULT_ACCEPT_LANGUAGE
    timeout_s: float = DEFAULT_TIMEOUT_S
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS
    backoff_base_s: float = DEFAULT_BACKOFF_BASE_S
    cancel_event: Any | None = None


@dataclass(frozen=True)
class VehicleHistoryRequestOptions:
    user_agent: str = DEFAULT_USER_AGENT
    accept_language: str = DEFAULT_ACCEPT_LANGUAGE
    timeout_s: float = DEFAULT_TIMEOUT_S
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS
    backoff_base_s: float = DEFAULT_BACKOFF_BASE_S


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


def _error_detail(error: HTTPError) -> str:
    detail = error.reason or "Unexpected upstream error."
    if error.fp is None:
        return str(detail)
    try:
        body = error.fp.read().decode("utf-8", "replace").strip()
    except Exception:
        return str(detail)
    return body or str(detail)


def _with_retry(
    action: Callable[[], T],
    settings: RetrySettings,
) -> T:
    total_attempts = max(0, settings.attempts) + 1
    last_error: Exception | None = None
    for attempt in range(total_attempts):
        _abort_if_requested(settings.label, settings.should_abort)
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
        delay = settings.base_delay * (2**attempt)
        LOGGER.warning(
            "Retrying %s after error (%s: %s). Attempt %s/%s in %.2fs.",
            settings.label,
            last_error.__class__.__name__,
            str(last_error),
            attempt + 1,
            total_attempts - 1,
            delay,
        )
        _sleep_with_abort(settings.label, delay, settings.should_abort)
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"{settings.label} failed without raising an exception")


def _abort_if_requested(label: str, should_abort: Callable[[], bool] | None) -> None:
    if should_abort is not None and should_abort():
        raise CancellationRequested(f"{label} cancelled.")


def _sleep_with_abort(label: str, delay: float, should_abort: Callable[[], bool] | None) -> None:
    slept = 0.0
    while slept < delay:
        _abort_if_requested(label, should_abort)
        remaining = min(0.1, delay - slept)
        time.sleep(remaining)
        slept += remaining
