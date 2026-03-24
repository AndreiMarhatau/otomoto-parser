from __future__ import annotations

import shutil
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from ..v1.parser import RUN_MODE_APPEND_NEWER, RUN_MODE_FULL, RUN_MODE_RESUME, parse_pages
from ..v1.otomoto_vehicle_identity import fetch_otomoto_listing_page_data
from ._service_analysis_helpers import default_red_flag_analyzer
from ._service_common import (
    ANALYSIS_STATUS_CANCELLING,
    ANALYSIS_STATUS_FAILED,
    ANALYSIS_STATUS_RUNNING,
    ParserRunner,
    ListingPageFetcher,
    RedFlagAnalyzer,
    REQUEST_STATUS_CATEGORIZING,
    REQUEST_STATUS_FAILED,
    REQUEST_STATUS_PENDING,
    REQUEST_STATUS_READY,
    REQUEST_STATUS_RUNNING,
    REPORT_STATUS_CANCELLING,
    REPORT_STATUS_RUNNING,
    SettingsState,
    configured_openai_api_key,
    utc_now,
)
from ._service_json import _read_json, _write_json
from ._service_store import RequestStore, SettingsStore, request_paths, settings_payload

DEFAULT_PARSER_OPTIONS = {
    "retry_attempts": 4,
    "backoff_base": 1.0,
    "delay_min": 0.0,
    "delay_max": 0.0,
    "request_timeout_s": 45.0,
}
@dataclass(frozen=True)
class ServiceDependencies:
    parser_runner: ParserRunner = parse_pages
    listing_page_fetcher: ListingPageFetcher = fetch_otomoto_listing_page_data
    red_flag_analyzer: RedFlagAnalyzer = default_red_flag_analyzer


class ServiceCoreMixin:
    def __init__(
        self,
        data_dir,
        dependencies: ServiceDependencies | None = None,
        parser_options: dict[str, Any] | None = None,
        **legacy_kwargs: Any,
    ) -> None:
        resolved_dependencies = _resolve_service_dependencies(dependencies, legacy_kwargs)
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.store = RequestStore(self.data_dir / "requests.json")
        self.settings_store = SettingsStore(self.data_dir / "settings.json")
        self.parser_runner = resolved_dependencies.parser_runner
        self.listing_page_fetcher = resolved_dependencies.listing_page_fetcher
        self.red_flag_analyzer = resolved_dependencies.red_flag_analyzer
        self.parser_options = {**DEFAULT_PARSER_OPTIONS, **(parser_options or {})}
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="parser-app")
        self._futures: dict[str, Future[Any]] = {}
        self._report_futures: dict[tuple[str, str], Future[Any]] = {}
        self._report_cancel_events: dict[tuple[str, str], threading.Event] = {}
        self._analysis_futures: dict[tuple[str, str, str], Future[Any]] = {}
        self._analysis_cancel_events: dict[tuple[str, str, str], threading.Event] = {}
        self._analysis_current_runs: dict[tuple[str, str], str] = {}
        self._lock = threading.Lock()
        self._request_locks: dict[str, threading.Lock] = {}
        self._recover_in_progress_requests()
        self._recover_in_progress_report_lookups()
        self._recover_in_progress_red_flag_analyses()

    def shutdown(self) -> None:
        with self._lock:
            for event in self._report_cancel_events.values():
                event.set()
            for event in self._analysis_cancel_events.values():
                event.set()
        self.executor.shutdown(wait=False, cancel_futures=True)

    def request_paths(self, request_id: str):
        return request_paths(self.data_dir, request_id)

    def list_requests(self) -> list[dict[str, Any]]:
        return self.store.list_requests()

    def get_request(self, request_id: str) -> dict[str, Any]:
        request = self.store.get_request(request_id)
        if request is None:
            raise KeyError(request_id)
        return request

    def get_settings(self) -> dict[str, Any]:
        return settings_payload(self.settings_store)

    def update_settings(self, *, openai_api_key: str | None) -> dict[str, Any]:
        cleaned = openai_api_key.strip() if isinstance(openai_api_key, str) else None
        self.settings_store.write(SettingsState(openai_api_key=cleaned or None))
        return self.get_settings()

    def _resolve_openai_api_key(self) -> str | None:
        return configured_openai_api_key(self.settings_store)

    def create_request(self, source_url: str) -> dict[str, Any]:
        request_id = uuid.uuid4().hex[:12]
        now = utc_now()
        paths = self.request_paths(request_id)
        request = {"id": request_id, "sourceUrl": source_url, "createdAt": now, "updatedAt": now, "status": REQUEST_STATUS_PENDING, "progressMessage": "Queued for initial import.", "pagesCompleted": 0, "resultsWritten": 0, "hasMore": True, "error": None, "lastRunMode": RUN_MODE_FULL, "resultsReady": False, "excelReady": False, "runDir": str(paths.request_dir), "resultsPath": str(paths.results_path), "statePath": str(paths.state_path), "categorizedPath": str(paths.categorized_path), "savedCategoriesPath": str(paths.saved_categories_path), "excelPath": str(paths.excel_path)}
        self.store.create_request(request)
        self._write_saved_categories(request_id, self._default_saved_categories())
        self.start_run(request_id, RUN_MODE_FULL)
        return self.get_request(request_id)

    def start_run(self, request_id: str, mode: str) -> dict[str, Any]:
        request = self.get_request(request_id)
        with self._lock:
            future = self._futures.get(request_id)
            if future is not None and not future.done():
                return request
            updated = self.store.update_request(request_id, status=REQUEST_STATUS_PENDING, progressMessage="Queued.", error=None, lastRunMode=mode, resultsReady=False if mode == RUN_MODE_FULL else request["resultsReady"], excelReady=False if mode == RUN_MODE_FULL else request["excelReady"])
            self._futures[request_id] = self.executor.submit(self._run_request, request_id, mode)
        return updated

    def choose_resume_mode(self, request_id: str) -> str:
        request = self.get_request(request_id)
        if request["status"] == REQUEST_STATUS_READY:
            return RUN_MODE_APPEND_NEWER
        if request["lastRunMode"] != RUN_MODE_APPEND_NEWER or not request["resultsReady"]:
            return RUN_MODE_RESUME
        state = _read_json(self.request_paths(request_id).state_path, {})
        return RUN_MODE_RESUME if isinstance(state.get("next_page"), int) and state.get("next_page") > 1 and state.get("has_more") is True else RUN_MODE_APPEND_NEWER

    def delete_request(self, request_id: str) -> None:
        with self._request_lock(request_id):
            self._ensure_request_not_active(request_id)
            request = self.get_request(request_id)
            shutil.rmtree(request["runDir"], ignore_errors=True)
            self.store.delete_request(request_id)
        with self._lock:
            self._request_locks.pop(request_id, None)

    def _recover_in_progress_requests(self) -> None:
        for request in self.store.list_requests():
            if request["status"] in {REQUEST_STATUS_PENDING, REQUEST_STATUS_RUNNING, REQUEST_STATUS_CATEGORIZING}:
                self.store.update_request(request["id"], status=REQUEST_STATUS_FAILED, error="The application stopped while this request was still running.", progressMessage="Interrupted during the previous run.")

    def _recover_in_progress_report_lookups(self) -> None:
        for request in self.store.list_requests():
            reports_dir = self.request_paths(request["id"]).reports_dir
            for status_path in reports_dir.glob("*.json") if reports_dir.exists() else []:
                status = _read_json(status_path, None)
                if isinstance(status, dict) and status.get("status") in {REPORT_STATUS_RUNNING, REPORT_STATUS_CANCELLING}:
                    self._write_json_recovered_report_status(status_path, status)

    def _recover_in_progress_red_flag_analyses(self) -> None:
        for request in self.store.list_requests():
            analyses_dir = self.request_paths(request["id"]).analyses_dir
            for status_path in analyses_dir.glob("*.json") if analyses_dir.exists() else []:
                status = _read_json(status_path, None)
                if isinstance(status, dict) and status.get("status") in {ANALYSIS_STATUS_RUNNING, ANALYSIS_STATUS_CANCELLING}:
                    _write_json(status_path, {"status": ANALYSIS_STATUS_FAILED, "lastAttemptAt": utc_now(), "lastError": "The previous red-flag analysis was interrupted. Please run it again.", "retrievedAt": status.get("retrievedAt"), "progressMessage": None})

    def _has_active_request_subtasks(self, request_id: str) -> bool:
        return any(active_request_id == request_id and not future.done() for (active_request_id, _), future in self._report_futures.items()) or any(active_request_id == request_id and not future.done() for (active_request_id, _, _), future in self._analysis_futures.items())

    def _has_active_analysis_for_listing(self, request_id: str, listing_id: str) -> bool:
        return any(active_request_id == request_id and active_listing_id == listing_id and not future.done() for (active_request_id, active_listing_id, _), future in self._analysis_futures.items())

    def _request_lock(self, request_id: str) -> threading.Lock:
        with self._lock:
            lock = self._request_locks.get(request_id)
            if lock is None:
                lock = threading.Lock()
                self._request_locks[request_id] = lock
            return lock

    def _ensure_request_not_active(self, request_id: str) -> None:
        with self._lock:
            future = self._futures.get(request_id)
            if future is not None and not future.done():
                raise RuntimeError("Cannot delete a request while it is still running.")
            if self._has_active_request_subtasks(request_id):
                raise RuntimeError("Cannot delete a request while a vehicle report lookup or red-flag analysis is still running.")


def _resolve_service_dependencies(
    dependencies: ServiceDependencies | None,
    legacy_kwargs: dict[str, Any],
) -> ServiceDependencies:
    if dependencies is None:
        return ServiceDependencies(**legacy_kwargs)
    if legacy_kwargs:
        raise TypeError("ServiceCoreMixin accepts either dependencies or legacy keyword arguments, not both.")
    return dependencies
