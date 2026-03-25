from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


CATEGORY_PRICE_OUT_OF_RANGE = "Price evaluation out of range"
CATEGORY_DATA_NOT_VERIFIED = "Data not verified"
CATEGORY_IMPORTED_FROM_US = "Imported from US"
CATEGORY_TO_BE_CHECKED = "To be checked"
CATEGORY_FAVORITES = "Favorites"

SYSTEM_CATEGORY_ORDER = [
    CATEGORY_PRICE_OUT_OF_RANGE,
    CATEGORY_IMPORTED_FROM_US,
    CATEGORY_DATA_NOT_VERIFIED,
    CATEGORY_TO_BE_CHECKED,
]
ASSIGNABLE_CATEGORY_ORDER = [CATEGORY_FAVORITES]
CUSTOM_CATEGORY_PREFIX = "custom:"

REQUEST_STATUS_PENDING = "pending"
REQUEST_STATUS_RUNNING = "running"
REQUEST_STATUS_CATEGORIZING = "categorizing"
REQUEST_STATUS_READY = "ready"
REQUEST_STATUS_FAILED = "failed"

REPORT_STATUS_IDLE = "idle"
REPORT_STATUS_RUNNING = "running"
REPORT_STATUS_SUCCESS = "success"
REPORT_STATUS_FAILED = "failed"
REPORT_STATUS_NEEDS_INPUT = "needs_input"
REPORT_STATUS_CANCELLING = "cancelling"
REPORT_STATUS_CANCELLED = "cancelled"
TERMINAL_REPORT_STATUSES = {
    REPORT_STATUS_SUCCESS,
    REPORT_STATUS_FAILED,
    REPORT_STATUS_NEEDS_INPUT,
    REPORT_STATUS_CANCELLED,
}

REPORT_MISSING_FIRST_REGISTRATION = "missing_first_registration"
REPORT_MISSING_REGISTRATION = "missing_registration"
REPORT_MISSING_REGISTRATION_AND_DATE = "missing_registration_and_date"
REPORT_UPSTREAM_404 = "upstream_404"
REPORT_PROGRESS_FETCHING_IDENTITY = "Fetching listing identity..."
REPORT_PROGRESS_FETCHING_REPORT = "Fetching vehicle history report..."

DEFAULT_REPORT_LOOKUP_DAYS_BACK = 120
DEFAULT_REPORT_LOOKUP_DAYS_FORWARD = 14
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_REDFLAG_MODEL = "gpt-5.4"
OPENAI_REDFLAG_SUPPORTING_MODEL = "gpt-5.4-mini"
STRICT_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

ANALYSIS_STATUS_IDLE = "idle"
ANALYSIS_STATUS_RUNNING = "running"
ANALYSIS_STATUS_SUCCESS = "success"
ANALYSIS_STATUS_FAILED = "failed"
ANALYSIS_STATUS_CANCELLING = "cancelling"
ANALYSIS_STATUS_CANCELLED = "cancelled"
TERMINAL_ANALYSIS_STATUSES = {
    ANALYSIS_STATUS_SUCCESS,
    ANALYSIS_STATUS_FAILED,
    ANALYSIS_STATUS_CANCELLED,
}
ANALYSIS_PROGRESS_COLLECTING_DATA = "Collecting listing data..."
ANALYSIS_PROGRESS_CALLING_MODEL = "Running GPT-5.4 red-flag analysis..."

ParserRunner = Callable[..., Any]
ListingPageFetcher = Callable[..., dict[str, Any]]
RedFlagAnalyzer = Callable[[str, dict[str, Any], threading.Event], dict[str, Any]]


class VehicleReportNeedsInput(Exception):
    pass


@dataclass(frozen=True)
class SettingsState:
    openai_api_key: str | None = None


@dataclass(frozen=True)
class RequestPaths:
    request_dir: Path
    results_path: Path
    state_path: Path
    categorized_path: Path
    saved_categories_path: Path
    excel_path: Path
    reports_dir: Path
    analyses_dir: Path


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def configured_openai_api_key(settings_store) -> str | None:
    stored = settings_store.read().openai_api_key
    if stored:
        return stored
    env_key = os.environ.get("OPENAI_API_KEY", "").strip()
    return env_key or None
