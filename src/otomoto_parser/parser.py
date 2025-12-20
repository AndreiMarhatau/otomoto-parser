from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, TypeVar
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

LOGGER = logging.getLogger("otomoto_parser")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)
DEFAULT_ACCEPT_LANGUAGE = "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"
DEFAULT_LOCALE = "pl-PL"
DEFAULT_TIMEZONE = "Europe/Warsaw"

RUN_MODE_RESUME = "resume"
RUN_MODE_APPEND_NEWER = "append-newer"
RUN_MODE_FULL = "full"
RUN_MODES = {RUN_MODE_RESUME, RUN_MODE_APPEND_NEWER, RUN_MODE_FULL}

ITEM_ID_PATTERN = re.compile(r'data-id=["\']([^"\']+)["\']')


@dataclass
class ParserState:
    start_url: str
    next_url: str
    pages_completed: int
    results_written: int
    pending_next: bool = False
    last_processed_url: str | None = None


def _normalize_start_url(url: str) -> str:
    parsed = urlparse(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "page"]
    normalized = parsed._replace(query=urlencode(query, doseq=True), fragment="")
    return urlunparse(normalized)


def _read_state(state_path: Path) -> ParserState | None:
    if not state_path.exists():
        return None
    data = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    start_url = data.get("start_url")
    next_url = data.get("next_url")
    pages_completed = data.get("pages_completed", 0)
    results_written = data.get("results_written", 0)
    pending_next = bool(data.get("pending_next", False))
    last_processed_url = data.get("last_processed_url")
    if not isinstance(next_url, str):
        return None
    return ParserState(
        start_url=str(start_url) if isinstance(start_url, str) else next_url,
        next_url=next_url,
        pages_completed=int(pages_completed),
        results_written=int(results_written),
        pending_next=pending_next,
        last_processed_url=(
            str(last_processed_url) if isinstance(last_processed_url, str) else None
        ),
    )


def _write_state(state_path: Path, state: ParserState) -> None:
    payload = {
        "start_url": state.start_url,
        "next_url": state.next_url,
        "pages_completed": state.pages_completed,
        "results_written": state.results_written,
        "pending_next": state.pending_next,
        "last_processed_url": state.last_processed_url,
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
        except (PlaywrightTimeoutError, PlaywrightError, RuntimeError) as exc:
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


def _extract_results(page, *, timeout_ms: int) -> list[str]:
    container = page.locator('[data-testid="search-results"]')
    container.wait_for(state="attached", timeout=timeout_ms)
    items = container.locator(":scope > *")
    count = items.count()
    results: list[str] = []
    for index in range(count):
        html = items.nth(index).evaluate("el => el.outerHTML")
        results.append(html)
    return results


def _extract_item_id(html: str) -> str | None:
    match = ITEM_ID_PATTERN.search(html)
    if not match:
        return None
    return match.group(1)


def _item_key_from_html(html: str) -> tuple[str, str | None]:
    item_id = _extract_item_id(html)
    if item_id:
        return f"id:{item_id}", item_id
    html_hash = hashlib.sha1(html.encode("utf-8")).hexdigest()
    return f"hash:{html_hash}", None


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
                key, _ = _item_key_from_html(html)
                keys.add(key)
    return keys


def _append_results(
    output_path: Path,
    page_url: str,
    results: Iterable[str],
    *,
    seen_item_keys: set[str],
) -> tuple[int, int]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0
    with output_path.open("a", encoding="utf-8") as handle:
        for item_index, html in enumerate(results):
            item_key, item_id = _item_key_from_html(html)
            if item_key in seen_item_keys:
                skipped += 1
                continue
            seen_item_keys.add(item_key)
            record = {
                "page_url": page_url,
                "item_index": item_index,
                "item_id": item_id,
                "item_key": item_key,
                "html": html,
            }
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
            written += 1
    return written, skipped


def _next_locator(page):
    return page.locator('[aria-label="Go to next Page"]').first


def _next_is_disabled(next_locator) -> bool:
    if next_locator.count() == 0:
        return True
    try:
        if next_locator.is_disabled():
            return True
    except Exception:
        pass
    aria_disabled = next_locator.get_attribute("aria-disabled")
    disabled_attr = next_locator.get_attribute("disabled")
    return aria_disabled == "true" or disabled_attr is not None


def _next_target_url(next_locator, current_url: str) -> str | None:
    for attr in ("href", "data-href", "data-url"):
        target = next_locator.get_attribute(attr)
        if target:
            return urljoin(current_url, target)
    return None


def _click_next(page, next_locator, *, delay_min: float, delay_max: float) -> None:
    if delay_max > 0:
        wait_time = random.uniform(delay_min, delay_max)
        LOGGER.info("Waiting %.2fs before going to next page.", wait_time)
        time.sleep(wait_time)
    previous_url = page.url
    target_url = _next_target_url(next_locator, previous_url)
    next_locator.click()
    try:
        page.wait_for_function(
            "previousUrl => window.location.href !== previousUrl",
            arg=previous_url,
            timeout=15000,
        )
    except PlaywrightTimeoutError:
        if target_url:
            page.goto(target_url, wait_until="networkidle", timeout=45000)
        else:
            raise
    page.wait_for_load_state("networkidle", timeout=45000)


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
    results_timeout_ms: int = 10000,
    debug_dir: Path | None = None,
    user_agent: str | None = DEFAULT_USER_AGENT,
    accept_language: str | None = DEFAULT_ACCEPT_LANGUAGE,
    locale: str | None = DEFAULT_LOCALE,
    timezone_id: str | None = DEFAULT_TIMEZONE,
    headless: bool = True,
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

    current_url = state.next_url if state else normalized_start_url
    pages_completed = state.pages_completed if state else 0
    results_written = state.results_written if state else 0
    pending_next = state.pending_next if state else False
    last_processed_url = state.last_processed_url if state else None
    if run_mode != RUN_MODE_RESUME:
        pending_next = False
        last_processed_url = None

    seen_item_keys = set()
    if run_mode != RUN_MODE_FULL:
        seen_item_keys = _load_existing_item_keys(output_path)
        if seen_item_keys:
            LOGGER.info("Loaded %s existing items for deduplication.", len(seen_item_keys))

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context_options: dict[str, object] = {}
        if user_agent:
            context_options["user_agent"] = user_agent
        if locale:
            context_options["locale"] = locale
        if timezone_id:
            context_options["timezone_id"] = timezone_id
        if accept_language:
            context_options["extra_http_headers"] = {
                "Accept-Language": accept_language
            }
        context = browser.new_context(**context_options)
        page = context.new_page()

        while True:
            if max_pages is not None and pages_completed >= max_pages:
                LOGGER.info("Reached max pages limit (%s).", max_pages)
                break

            def load_page(url: str) -> None:
                page.goto(url, wait_until="networkidle", timeout=45000)

            if pending_next and last_processed_url:
                _with_retry(
                    lambda: load_page(last_processed_url),
                    attempts=retry_attempts,
                    base_delay=backoff_base,
                    label="resume load page",
                    logger=LOGGER,
                )
                next_button = _next_locator(page)
                if next_button.count() == 0:
                    pending_next = False
                    last_processed_url = None
                    current_url = page.url
                    LOGGER.info("No next page available after resume.")
                    break
                if _next_is_disabled(next_button):
                    pending_next = False
                    last_processed_url = None
                    current_url = page.url
                    LOGGER.info("No next page available after resume.")
                    break

                _with_retry(
                    lambda: _click_next(
                        page,
                        next_button,
                        delay_min=delay_min,
                        delay_max=delay_max,
                    ),
                    attempts=retry_attempts,
                    base_delay=backoff_base,
                    label="resume click next",
                    logger=LOGGER,
                )
                current_url = page.url
                pending_next = False
                last_processed_url = None
            else:
                LOGGER.info("Loading page: %s", current_url)
                _with_retry(
                    lambda: load_page(current_url),
                    attempts=retry_attempts,
                    base_delay=backoff_base,
                    label="load page",
                    logger=LOGGER,
                )

            def extract_with_context() -> list[str]:
                try:
                    return _extract_results(page, timeout_ms=results_timeout_ms)
                except Exception as exc:
                    LOGGER.error("Failed to extract results on %s.", page.url)
                    if debug_dir:
                        debug_dir.mkdir(parents=True, exist_ok=True)
                        safe_ts = str(int(time.time()))
                        basename = f"extract_error_{pages_completed + 1}_{safe_ts}"
                        html_path = debug_dir / f"{basename}.html"
                        png_path = debug_dir / f"{basename}.png"
                        try:
                            html_path.write_text(page.content(), encoding="utf-8")
                            LOGGER.error("Saved page HTML to %s", html_path)
                        except Exception as dump_exc:
                            LOGGER.error("Failed to save HTML dump: %s", dump_exc)
                        try:
                            page.screenshot(path=str(png_path), full_page=True)
                            LOGGER.error("Saved page screenshot to %s", png_path)
                        except Exception as dump_exc:
                            LOGGER.error("Failed to save screenshot: %s", dump_exc)
                    try:
                        title = page.title()
                    except Exception:
                        title = "<unavailable>"
                    try:
                        container_count = page.locator(
                            '[data-testid="search-results"]'
                        ).count()
                    except Exception:
                        container_count = -1
                    try:
                        content_len = len(page.content())
                    except Exception:
                        content_len = -1
                    LOGGER.error(
                        "Page url=%s title=%s container_count=%s content_len=%s error=%s: %s",
                        page.url,
                        title,
                        container_count,
                        content_len,
                        exc.__class__.__name__,
                        str(exc),
                    )
                    raise

            results = _with_retry(
                extract_with_context,
                attempts=retry_attempts,
                base_delay=backoff_base,
                label="extract results",
                logger=LOGGER,
            )
            LOGGER.info("Found %s results on %s.", len(results), page.url)

            written, skipped = _append_results(
                output_path,
                page.url,
                results,
                seen_item_keys=seen_item_keys,
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
            if run_mode == RUN_MODE_APPEND_NEWER and results and written == 0:
                LOGGER.info("All listings on this page already exist; stopping append-newer mode.")
                break

            if run_mode in {RUN_MODE_RESUME, RUN_MODE_FULL}:
                _write_state(
                    state_path,
                    ParserState(
                        start_url=normalized_start_url,
                        next_url=page.url,
                        pages_completed=pages_completed,
                        results_written=results_written,
                        pending_next=True,
                        last_processed_url=page.url,
                    ),
                )
                pending_next = True
                last_processed_url = page.url

            next_button = _next_locator(page)
            if next_button.count() == 0:
                LOGGER.info("Next page button not found. Stopping.")
                break
            if _next_is_disabled(next_button):
                LOGGER.info("Next page button disabled. Stopping.")
                break

            _with_retry(
                lambda: _click_next(
                    page,
                    next_button,
                    delay_min=delay_min,
                    delay_max=delay_max,
                ),
                attempts=retry_attempts,
                base_delay=backoff_base,
                label="click next",
                logger=LOGGER,
            )
            current_url = page.url
            pending_next = False
            last_processed_url = None
            LOGGER.info("Moved to next page: %s", current_url)

            if run_mode in {RUN_MODE_RESUME, RUN_MODE_FULL}:
                _write_state(
                    state_path,
                    ParserState(
                        start_url=normalized_start_url,
                        next_url=current_url,
                        pages_completed=pages_completed,
                        results_written=results_written,
                        pending_next=False,
                        last_processed_url=None,
                    ),
                )

        context.close()
        browser.close()

    final_state = ParserState(
        start_url=normalized_start_url,
        next_url=current_url,
        pages_completed=pages_completed,
        results_written=results_written,
        pending_next=False,
        last_processed_url=None,
    )
    if run_mode in {RUN_MODE_RESUME, RUN_MODE_FULL}:
        _write_state(state_path, final_state)
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
        help="Retry attempts for navigation and clicks",
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
        help="Minimum delay in seconds before going to the next page",
    )
    parser.add_argument(
        "--delay-max",
        type=float,
        default=20.0,
        help="Maximum delay in seconds before going to the next page",
    )
    parser.add_argument(
        "--results-timeout-ms",
        type=int,
        default=10000,
        help="Timeout in ms for locating the results container",
    )
    parser.add_argument(
        "--debug-dir",
        default=None,
        help="Directory to store HTML/screenshot dumps on extraction errors",
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
        "--locale",
        default=DEFAULT_LOCALE,
        help="Browser locale (e.g., pl-PL)",
    )
    parser.add_argument(
        "--timezone",
        default=DEFAULT_TIMEZONE,
        help="Browser timezone (e.g., Europe/Warsaw)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser in headed mode",
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
        run_root = Path(args.output_dir)
        run_dir_name = _normalize_start_url(url)
        parsed = urlparse(run_dir_name)
        base_name = f"{parsed.netloc}-{parsed.path.strip('/') or 'root'}"
        base_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", base_name).strip("-").lower()
        digest = hashlib.sha1(run_dir_name.encode("utf-8")).hexdigest()[:10]
        run_dir = run_root / f"{base_name}-{digest}"
        output_path = run_dir / "results.jsonl"
        state_path = run_dir / "state.json"

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
        results_timeout_ms=args.results_timeout_ms,
        debug_dir=Path(args.debug_dir) if args.debug_dir else None,
        user_agent=args.user_agent,
        accept_language=args.accept_language,
        locale=args.locale,
        timezone_id=args.timezone,
        headless=not args.headed,
    )
    print(
        json.dumps(
            {
                "pages_completed": state.pages_completed,
                "results_written": state.results_written,
                "next_url": state.next_url,
            },
            indent=2,
        )
    )


__all__ = ["parse_pages", "build_arg_parser", "main"]
