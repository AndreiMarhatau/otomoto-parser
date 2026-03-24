from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any

from ..v1.history_report import CancellationRequested
from ._service_common import (
    ANALYSIS_PROGRESS_CALLING_MODEL,
    ANALYSIS_PROGRESS_COLLECTING_DATA,
    ANALYSIS_STATUS_CANCELLED,
    ANALYSIS_STATUS_CANCELLING,
    ANALYSIS_STATUS_FAILED,
    ANALYSIS_STATUS_IDLE,
    ANALYSIS_STATUS_RUNNING,
    ANALYSIS_STATUS_SUCCESS,
    OPENAI_REDFLAG_MODEL,
    TERMINAL_ANALYSIS_STATUSES,
    utc_now,
)
from ._service_json import _build_report_snapshot_id, _read_json, _write_json


class ServiceAnalysisMixin:
    def get_red_flag_analysis(self, request_id: str, listing_id: str) -> dict[str, Any]:
        with self._request_lock(request_id):
            return self._build_red_flag_analysis_state_payload(request_id, self._resolve_listing_for_report(request_id, listing_id))

    def start_red_flag_analysis(self, request_id: str, listing_id: str) -> dict[str, Any]:
        with self._request_lock(request_id):
            listing = self._resolve_listing_for_report(request_id, listing_id)
            canonical_listing_id = listing["id"]
            api_key = self._resolve_openai_api_key()
            if not api_key:
                raise RuntimeError("Configure an OpenAI API key in Settings before running red-flag analysis.")
            run_id = self._reserve_analysis_run(request_id, canonical_listing_id)
            cache_path = self._red_flag_analysis_path(request_id, canonical_listing_id)
            if cache_path.exists():
                cache_path.unlink()
            self._write_red_flag_analysis_status(
                self._red_flag_status_path(request_id, canonical_listing_id),
                {"status": ANALYSIS_STATUS_RUNNING, "progress_message": ANALYSIS_PROGRESS_COLLECTING_DATA, "run_id": run_id},
            )
            self._start_red_flag_analysis_job({"request_id": request_id, "listing_id": canonical_listing_id, "run_id": run_id, "listing": listing, "api_key": api_key})
            return self._build_red_flag_analysis_state_payload(request_id, listing)

    def cancel_red_flag_analysis(self, request_id: str, listing_id: str) -> dict[str, Any]:
        with self._request_lock(request_id):
            listing = self._resolve_listing_for_report(request_id, listing_id)
            canonical_listing_id = listing["id"]
            status_path = self._red_flag_status_path(request_id, canonical_listing_id)
            active_run_id, future_key = self._active_analysis_future_key(request_id, canonical_listing_id)
            with self._lock:
                active_future = self._analysis_futures.get(future_key)
                cancel_event = self._analysis_cancel_events.get(future_key)
                if active_future is None or active_future.done() or cancel_event is None:
                    raise RuntimeError("No active red-flag analysis is currently running for this listing.")
                cancel_event.set()
                if active_future.cancel():
                    self._analysis_futures.pop(future_key, None)
                    self._analysis_cancel_events.pop(future_key, None)
                    self._write_red_flag_analysis_status(status_path, {"status": ANALYSIS_STATUS_CANCELLED, "error": "Red-flag analysis was cancelled.", "progress_message": None, "run_id": active_run_id})
                    return self._build_red_flag_analysis_state_payload(request_id, listing)
            latest_status = _read_json(status_path, {})
            if latest_status.get("status") in TERMINAL_ANALYSIS_STATUSES:
                return self._build_red_flag_analysis_state_payload(request_id, listing)
            self._write_red_flag_analysis_status(status_path, {"status": ANALYSIS_STATUS_CANCELLING, "error": "Red-flag analysis cancellation requested.", "progress_message": "Cancelling red-flag analysis...", "run_id": active_run_id})
            return self._build_red_flag_analysis_state_payload(request_id, listing)

    def _red_flag_analysis_path(self, request_id: str, listing_id: str) -> Path:
        return self.request_paths(request_id).analyses_dir / f"{__import__('hashlib').sha256(f'{listing_id}:analysis'.encode('utf-8')).hexdigest()}.json"

    def _red_flag_status_path(self, request_id: str, listing_id: str) -> Path:
        return self.request_paths(request_id).analyses_dir / f"{__import__('hashlib').sha256(f'{listing_id}:analysis:status'.encode('utf-8')).hexdigest()}.json"

    def _write_red_flag_analysis_status(self, path: Path, status_data: dict[str, Any]) -> None:
        _write_json(path, {"runId": status_data.get("run_id"), "status": status_data["status"], "lastAttemptAt": utc_now(), "lastError": status_data.get("error"), "retrievedAt": status_data.get("retrieved_at"), "progressMessage": status_data.get("progress_message")})

    def _build_red_flag_analysis_state_payload(self, request_id: str, listing: dict[str, Any]) -> dict[str, Any]:
        current_status = _read_json(self._red_flag_status_path(request_id, str(listing["id"])), {})
        cached = _read_json(self._red_flag_analysis_path(request_id, str(listing["id"])), None)
        report_payload = _read_json(self._vehicle_report_path(request_id, str(listing["id"])), None)
        current_report_snapshot_id = _build_report_snapshot_id(report_payload)
        if isinstance(cached, dict) and (cached.get("reportSnapshotId") or _build_report_snapshot_id(cached.get("vehicleReport"))) == current_report_snapshot_id:
            return self._normalize_red_flag_analysis_payload(cached)
        if cached is not None:
            return {"listingId": listing["id"], "listingUrl": listing.get("url"), "listingTitle": listing.get("title"), "retrievedAt": cached.get("retrievedAt") if isinstance(cached, dict) else None, "lastAttemptAt": cached.get("retrievedAt") if isinstance(cached, dict) else None, "status": ANALYSIS_STATUS_IDLE, "progressMessage": None, "error": "Analysis is outdated because the vehicle report changed. Run it again.", "analysis": None, "model": OPENAI_REDFLAG_MODEL, "reportReady": report_payload is not None, "reportSnapshotId": current_report_snapshot_id, "analysisReportSnapshotId": cached.get("reportSnapshotId") if isinstance(cached, dict) else None, "stale": True, "apiKeyConfigured": self._resolve_openai_api_key() is not None}
        return {"listingId": listing["id"], "listingUrl": listing.get("url"), "listingTitle": listing.get("title"), "retrievedAt": current_status.get("retrievedAt"), "lastAttemptAt": current_status.get("lastAttemptAt"), "status": current_status.get("status") or ANALYSIS_STATUS_IDLE, "progressMessage": current_status.get("progressMessage"), "error": current_status.get("lastError"), "analysis": None, "model": OPENAI_REDFLAG_MODEL, "reportReady": report_payload is not None, "reportSnapshotId": current_report_snapshot_id, "analysisReportSnapshotId": current_status.get("reportSnapshotId"), "stale": False, "apiKeyConfigured": self._resolve_openai_api_key() is not None}

    def _normalize_red_flag_analysis_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        analysis = normalized.get("analysis")
        if isinstance(analysis, dict):
            normalized["analysis"] = {**analysis, "redFlags": [str(value).strip() for value in analysis.get("redFlags", []) if str(value).strip()], "warnings": [str(value).strip() for value in analysis.get("warnings", []) if str(value).strip()], "greenFlags": [str(value).strip() for value in analysis.get("greenFlags", []) if str(value).strip()], "webSearchUsed": bool(analysis.get("webSearchUsed"))}
        return normalized

    def _reserve_analysis_run(self, request_id: str, canonical_listing_id: str) -> str:
        listing_key = (request_id, canonical_listing_id)
        with self._lock:
            active_run_id = self._analysis_current_runs.get(listing_key)
            active_future = self._analysis_futures.get((request_id, canonical_listing_id, active_run_id)) if active_run_id else None
            active_cancel_event = self._analysis_cancel_events.get((request_id, canonical_listing_id, active_run_id)) if active_run_id else None
            if active_future is not None and not active_future.done():
                if active_cancel_event is not None and active_cancel_event.is_set():
                    raise RuntimeError("Red-flag analysis cancellation is still in progress for this listing.")
                raise RuntimeError("A red-flag analysis is already running for this listing.")
            run_id = uuid.uuid4().hex
            self._analysis_current_runs[listing_key] = run_id
            return run_id

    def _active_analysis_future_key(self, request_id: str, canonical_listing_id: str) -> tuple[str | None, tuple[str, str, str] | None]:
        with self._lock:
            active_run_id = self._analysis_current_runs.get((request_id, canonical_listing_id))
        return active_run_id, (request_id, canonical_listing_id, active_run_id) if active_run_id else None

    def _is_latest_red_flag_run(self, request_id: str, listing_id: str, run_id: str) -> bool:
        with self._lock:
            return self._analysis_current_runs.get((request_id, listing_id)) == run_id

    def _write_latest_red_flag_analysis_status(self, run_context: dict[str, Any], status_path: Path, status_data: dict[str, Any]) -> None:
        if self._is_latest_red_flag_run(run_context["request_id"], run_context["listing_id"], run_context["run_id"]):
            self._write_red_flag_analysis_status(status_path, {**status_data, "run_id": run_context["run_id"]})

    def _build_red_flag_model_input(self, request_id: str, listing_id: str) -> dict[str, Any]:
        listing = self._resolve_listing_for_report(request_id, listing_id)
        record = self._find_listing_record(request_id, listing_id)
        listing_page = self.listing_page_fetcher(listing.get("url"), timeout_s=float(self.parser_options.get("request_timeout_s", 45.0))) if isinstance(listing.get("url"), str) and listing.get("url") else None
        report_payload = _read_json(self._vehicle_report_path(request_id, str(listing_id)), None)
        report_snapshot_id = _build_report_snapshot_id(report_payload)
        return {"listing": listing, "searchResultRaw": record, "listingPageRaw": listing_page, "vehicleReport": report_payload, "reportSnapshotId": report_snapshot_id, "notes": {"vehicleReportReady": report_payload is not None, "reportSnapshotId": report_snapshot_id, "generatedAt": utc_now()}}

    def _start_red_flag_analysis_job(self, analysis_job: dict[str, Any]) -> bool:
        future_key = (analysis_job["request_id"], analysis_job["listing_id"], analysis_job["run_id"])
        with self._lock:
            cancel_event = threading.Event()
            self._analysis_cancel_events[future_key] = cancel_event
            self._analysis_futures[future_key] = self.executor.submit(self._run_red_flag_analysis, {**analysis_job, "cancel_event": cancel_event})
            return True

    def _run_red_flag_analysis(self, analysis_job: dict[str, Any]) -> None:
        status_path = self._red_flag_status_path(analysis_job["request_id"], analysis_job["listing_id"])
        cache_path = self._red_flag_analysis_path(analysis_job["request_id"], analysis_job["listing_id"])
        try:
            model_input = self._build_red_flag_model_input(analysis_job["request_id"], analysis_job["listing_id"])
            if analysis_job["cancel_event"].is_set():
                return self._write_latest_red_flag_analysis_status(analysis_job, status_path, {"status": ANALYSIS_STATUS_CANCELLED, "error": "Red-flag analysis was cancelled."})
            self._write_latest_red_flag_analysis_status(analysis_job, status_path, {"status": ANALYSIS_STATUS_RUNNING, "progress_message": ANALYSIS_PROGRESS_CALLING_MODEL})
            analysis = self.red_flag_analyzer(analysis_job["api_key"], model_input, analysis_job["cancel_event"])
            if analysis_job["cancel_event"].is_set():
                return self._write_latest_red_flag_analysis_status(analysis_job, status_path, {"status": ANALYSIS_STATUS_CANCELLED, "error": "Red-flag analysis was cancelled."})
            payload = {"listingId": analysis_job["listing"]["id"], "listingUrl": analysis_job["listing"].get("url"), "listingTitle": analysis_job["listing"].get("title"), "retrievedAt": utc_now(), "status": ANALYSIS_STATUS_SUCCESS, "error": None, "model": OPENAI_REDFLAG_MODEL, "reportReady": bool(model_input.get("vehicleReport")), "reportSnapshotId": model_input.get("reportSnapshotId"), "apiKeyConfigured": True, "analysis": {"summary": str(analysis.get("summary") or "").strip(), "redFlags": [str(value).strip() for value in analysis.get("redFlags", []) if str(value).strip()], "warnings": [str(value).strip() for value in analysis.get("warnings", []) if str(value).strip()], "greenFlags": [str(value).strip() for value in analysis.get("greenFlags", []) if str(value).strip()], "webSearchUsed": bool(analysis.get("webSearchUsed"))}}
            current_report_snapshot_id = _build_report_snapshot_id(_read_json(self._vehicle_report_path(analysis_job["request_id"], analysis_job["listing_id"]), None))
            if self._is_latest_red_flag_run(analysis_job["request_id"], analysis_job["listing_id"], analysis_job["run_id"]) and current_report_snapshot_id == model_input.get("reportSnapshotId"):
                _write_json(cache_path, payload)
                self._write_red_flag_analysis_status(status_path, {"status": ANALYSIS_STATUS_SUCCESS, "retrieved_at": payload["retrievedAt"], "run_id": analysis_job["run_id"]})
            elif self._is_latest_red_flag_run(analysis_job["request_id"], analysis_job["listing_id"], analysis_job["run_id"]):
                self._write_red_flag_analysis_status(status_path, {"status": ANALYSIS_STATUS_IDLE, "error": "Analysis finished after the vehicle report changed. Run it again.", "run_id": analysis_job["run_id"]})
        except CancellationRequested:
            self._write_latest_red_flag_analysis_status(analysis_job, status_path, {"status": ANALYSIS_STATUS_CANCELLED, "error": "Red-flag analysis was cancelled."})
        except Exception as exc:
            self._write_latest_red_flag_analysis_status(analysis_job, status_path, {"status": ANALYSIS_STATUS_FAILED, "error": f"Red-flag analysis failed: {exc}"})
        finally:
            with self._lock:
                self._analysis_futures.pop((analysis_job["request_id"], analysis_job["listing_id"], analysis_job["run_id"]), None)
                self._analysis_cancel_events.pop((analysis_job["request_id"], analysis_job["listing_id"], analysis_job["run_id"]), None)
                if self._analysis_current_runs.get((analysis_job["request_id"], analysis_job["listing_id"])) == analysis_job["run_id"] and analysis_job["cancel_event"].is_set():
                    self._analysis_current_runs.pop((analysis_job["request_id"], analysis_job["listing_id"]), None)
