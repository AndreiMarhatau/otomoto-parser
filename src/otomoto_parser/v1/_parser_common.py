from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


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

CATEGORY_SLUG_TO_ID = {"osobowe": "29"}
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


@dataclass(frozen=True)
class ParserRunOptions:
    run_mode: str = RUN_MODE_RESUME
    max_pages: int | None = None
    retry_attempts: int = 4
    backoff_base: float = 1.0
    delay_min: float = 10.0
    delay_max: float = 20.0
    request_timeout_s: float = 45.0
    user_agent: str | None = DEFAULT_USER_AGENT
    accept_language: str | None = DEFAULT_ACCEPT_LANGUAGE
    request_func: RequestFunc | None = None
    page_request_func: PageRequestFunc | None = None
    progress_callback: ProgressCallback | None = None


ProgressCallback = Callable[[dict[str, Any]], None]
RequestFunc = Callable[[dict, dict[str, str], float], dict]
PageRequestFunc = Callable[[str, dict[str, str], float], str]


def _normalize_start_url(url: str) -> str:
    parsed = urlparse(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key not in {"page", "search[page]"}]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True), fragment=""))


def _url_with_page(url: str, page: int) -> str:
    parsed = urlparse(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "page"]
    if page > 1:
        query.append(("page", str(page)))
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True), fragment=""))


def build_run_paths(start_url: str, output_dir: str | Path = "runs") -> tuple[Path, Path, Path]:
    normalized = _normalize_start_url(start_url)
    parsed = urlparse(normalized)
    base_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", f"{parsed.netloc}-{parsed.path.strip('/') or 'root'}").strip("-").lower()
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10]
    run_dir = Path(output_dir) / f"{base_name}-{digest}"
    return run_dir, run_dir / "results.jsonl", run_dir / "state.json"


def _page_from_url(url: str) -> int:
    for key, value in parse_qsl(urlparse(url).query, keep_blank_values=True):
        if key == "page" and value:
            try:
                return int(value)
            except ValueError:
                break
    return 1


def _emit_progress(callback: ProgressCallback | None, event: str, **payload: Any) -> None:
    if callback is not None:
        callback({"event": event, **payload})
