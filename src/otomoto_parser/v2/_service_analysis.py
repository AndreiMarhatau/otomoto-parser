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
from ._service_listing_helpers import _location_display, _param_display, _param_map, _price_evaluation_display, _price_fields

_LISTING_PARAMETER_KEYS = (
    "make",
    "model",
    "version",
    "generation",
    "year",
    "mileage",
    "fuel_type",
    "gearbox",
    "body_type",
    "engine_capacity",
    "engine_power",
    "drive",
    "doors_no",
    "seats_no",
    "color",
    "registered",
    "country_origin",
    "condition",
    "origin_country",
)
_IDENTIFIER_PARAMETER_ALIASES = {
    "vin": "vin",
    "registration": "registrationNumber",
    "date_registration": "firstRegistrationDate",
}
_MAX_SHORT_DESCRIPTION_LENGTH = 600
_MAX_DESCRIPTION_LENGTH = 3000
_MAX_TIMELINE_EVENTS = 8
_MAX_TIMELINE_EVENT_FIELDS = ("date", "type", "label", "mileage", "country", "source")


def _compact_dict(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item not in (None, "", [], {})}


def _truncate_text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    if not normalized:
        return None
    if len(normalized) <= limit:
        return normalized
    if limit <= 3:
        return normalized[:limit]
    return f"{normalized[: limit - 3].rstrip()}..."


def _seller_payload(raw_seller: Any) -> dict[str, Any] | str | None:
    if isinstance(raw_seller, str) and raw_seller:
        return raw_seller
    if not isinstance(raw_seller, dict):
        return None
    return _compact_dict(
        {
            "id": raw_seller.get("id"),
            "name": raw_seller.get("name"),
            "websiteUrl": raw_seller.get("websiteUrl"),
            "isCreditIntermediary": raw_seller.get("isCreditIntermediary"),
        }
    )


def _parameter_value_from_detail_entry(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return None
    direct_value = entry.get("displayValue") or entry.get("label")
    if direct_value not in (None, ""):
        return str(direct_value)
    values = entry.get("values")
    if isinstance(values, list):
        for item in values:
            if not isinstance(item, dict):
                continue
            candidate = item.get("label") or item.get("displayValue")
            if candidate not in (None, ""):
                return str(candidate)
    raw_value = entry.get("value")
    if raw_value not in (None, ""):
        return str(raw_value)
    if isinstance(values, list):
        for item in values:
            if not isinstance(item, dict):
                continue
            candidate = item.get("value")
            if candidate not in (None, ""):
                return str(candidate)
    return None


def _selected_parameter_payload(parameters: list[dict[str, Any]] | None) -> dict[str, Any]:
    parameter_map = _param_map(parameters)
    return _compact_dict({key: _param_display(parameter_map, key) for key in _LISTING_PARAMETER_KEYS})


def _selected_detail_parameter_payload(parameters_dict: Any) -> dict[str, Any]:
    if not isinstance(parameters_dict, dict):
        return {}
    return _compact_dict({key: _parameter_value_from_detail_entry(parameters_dict.get(key)) for key in _LISTING_PARAMETER_KEYS})


def _identifier_payload(
    listing: dict[str, Any],
    search_parameters: list[dict[str, Any]] | None,
    detail_parameters: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    search_parameter_map = _param_map(search_parameters)
    detail_parameter_map = _param_map(detail_parameters)
    identifiers: dict[str, Any] = {}
    for source_key, target_key in _IDENTIFIER_PARAMETER_ALIASES.items():
        value = (
            listing.get(target_key)
            or _param_display(search_parameter_map, source_key)
            or _param_display(detail_parameter_map, source_key)
        )
        if value not in (None, ""):
            identifiers[target_key] = value
    return identifiers


def _listing_payload(listing: dict[str, Any], record: dict[str, Any], listing_page: dict[str, Any] | None) -> dict[str, Any]:
    node = record.get("node") if isinstance(record.get("node"), dict) else {}
    detail_parameters = listing_page.get("parameters") if isinstance(listing_page, dict) else None
    detail_parameters_dict = listing_page.get("parametersDict") if isinstance(listing_page, dict) else None
    search_parameters = node.get("parameters")
    merged_parameters = _selected_parameter_payload(search_parameters)
    detail_parameter_payload = _selected_parameter_payload(detail_parameters)
    detail_parameter_dict_payload = _selected_detail_parameter_payload(detail_parameters_dict)
    for key, value in detail_parameter_payload.items():
        merged_parameters[key] = value
    for key, value in detail_parameter_dict_payload.items():
        merged_parameters[key] = value
    return _compact_dict(
        {
            "id": listing.get("id"),
            "url": listing.get("url"),
            "title": listing.get("title") or node.get("title") or (listing_page or {}).get("title"),
            "location": listing.get("location") or _location_display(node.get("location")) or _location_display((listing_page or {}).get("location")),
            "createdAt": node.get("createdAt") or (listing_page or {}).get("createdAt"),
            "price": _compact_dict(
                {
                    "amount": _price_fields(node)[0],
                    "currency": _price_fields(node)[1],
                    "evaluation": _price_evaluation_display(node.get("priceEvaluation")),
                }
            ),
            "seller": _seller_payload(node.get("sellerLink")) or _seller_payload((listing_page or {}).get("sellerLink")),
            "dataVerified": node.get("cepikVerified"),
            "shortDescription": _truncate_text(node.get("shortDescription"), _MAX_SHORT_DESCRIPTION_LENGTH),
            "description": _truncate_text((listing_page or {}).get("description"), _MAX_DESCRIPTION_LENGTH),
            "identifiers": _identifier_payload(listing, search_parameters, detail_parameters),
            "parameters": merged_parameters,
            "badges": [str(item.get("name")).strip() for item in node.get("valueAddedServices", []) if isinstance(item, dict) and str(item.get("name") or "").strip()],
        }
    )


def _timeline_payload(timeline_data: Any) -> dict[str, Any] | None:
    if not isinstance(timeline_data, dict):
        return None
    events = ((timeline_data.get("timelineData") or {}).get("events")) if isinstance(timeline_data.get("timelineData"), dict) else None
    if not isinstance(events, list):
        return None
    compact_events = []
    event_types: list[str] = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if isinstance(event_type, str) and event_type and event_type not in event_types:
            event_types.append(event_type)
        if index >= _MAX_TIMELINE_EVENTS:
            continue
        compact_event = _compact_dict({field: event.get(field) for field in _MAX_TIMELINE_EVENT_FIELDS})
        if compact_event:
            compact_events.append(compact_event)
    return _compact_dict({"eventCount": len(events), "eventTypes": event_types, "events": compact_events})


def _vehicle_report_payload(report_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(report_payload, dict):
        return None
    report = report_payload.get("report") if isinstance(report_payload.get("report"), dict) else {}
    technical_data = report.get("technical_data") if isinstance(report.get("technical_data"), dict) else {}
    technical_data_root = technical_data.get("technicalData") if isinstance(technical_data.get("technicalData"), dict) else {}
    basic_data = technical_data_root.get("basicData") if isinstance(technical_data_root.get("basicData"), dict) else {}
    ownership_history = technical_data_root.get("ownershipHistory") if isinstance(technical_data_root.get("ownershipHistory"), dict) else {}
    return _compact_dict(
        {
            "identity": report_payload.get("identity"),
            "summary": report_payload.get("summary"),
            "sourceStatus": _compact_dict(
                {
                    "apiVersion": report.get("api_version"),
                    "autodnaAvailable": report_payload.get("summary", {}).get("autodnaAvailable") if isinstance(report_payload.get("summary"), dict) else None,
                    "carfaxAvailable": report_payload.get("summary", {}).get("carfaxAvailable") if isinstance(report_payload.get("summary"), dict) else None,
                    "autodnaUnavailable": report_payload.get("summary", {}).get("autodnaUnavailable") if isinstance(report_payload.get("summary"), dict) else None,
                    "carfaxUnavailable": report_payload.get("summary", {}).get("carfaxUnavailable") if isinstance(report_payload.get("summary"), dict) else None,
                }
            ),
            "technicalData": _compact_dict(
                {
                    "basicData": _compact_dict(
                        {
                            "make": basic_data.get("make"),
                            "model": basic_data.get("model"),
                            "type": basic_data.get("type"),
                            "modelYear": basic_data.get("modelYear"),
                            "fuel": basic_data.get("fuel"),
                            "engineCapacity": basic_data.get("engineCapacity"),
                            "enginePower": basic_data.get("enginePower"),
                            "bodyType": basic_data.get("bodyType"),
                            "color": basic_data.get("color"),
                        }
                    ),
                    "ownershipHistory": _compact_dict(
                        {
                            "numberOfOwners": ownership_history.get("numberOfOwners"),
                            "numberOfCoowners": ownership_history.get("numberOfCoowners"),
                            "dateOfLastOwnershipChange": ownership_history.get("dateOfLastOwnershipChange"),
                        }
                    ),
                }
            ),
            "timeline": _timeline_payload(report.get("timeline_data")),
            "autodnaSummary": report.get("autodna_data", {}).get("summary") if isinstance(report.get("autodna_data"), dict) else None,
            "carfaxSummary": report.get("carfax_data", {}).get("summary") if isinstance(report.get("carfax_data"), dict) else None,
        }
    )


class ServiceAnalysisMixin:
    def _default_red_flag_models(self, model_name: str | None = None) -> dict[str, str]:
        resolved_model = str(model_name or OPENAI_REDFLAG_MODEL)
        return {"redFlags": resolved_model, "warningsAndGreenFlags": resolved_model}

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
            normalized["models"] = normalized.get("models") if isinstance(normalized.get("models"), dict) else self._default_red_flag_models(normalized.get("model"))
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
        return {
            "listing": _listing_payload(listing, record, listing_page if isinstance(listing_page, dict) else None),
            "vehicleReport": _vehicle_report_payload(report_payload),
            "reportSnapshotId": report_snapshot_id,
            "notes": {
                "vehicleReportReady": report_payload is not None,
                "reportSnapshotId": report_snapshot_id,
                "generatedAt": utc_now(),
            },
        }

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
            payload = {"listingId": analysis_job["listing"]["id"], "listingUrl": analysis_job["listing"].get("url"), "listingTitle": analysis_job["listing"].get("title"), "retrievedAt": utc_now(), "status": ANALYSIS_STATUS_SUCCESS, "error": None, "model": OPENAI_REDFLAG_MODEL, "models": analysis.get("models") if isinstance(analysis.get("models"), dict) else self._default_red_flag_models(), "reportReady": bool(model_input.get("vehicleReport")), "reportSnapshotId": model_input.get("reportSnapshotId"), "apiKeyConfigured": True, "analysis": {"summary": str(analysis.get("summary") or "").strip(), "redFlags": [str(value).strip() for value in analysis.get("redFlags", []) if str(value).strip()], "warnings": [str(value).strip() for value in analysis.get("warnings", []) if str(value).strip()], "greenFlags": [str(value).strip() for value in analysis.get("greenFlags", []) if str(value).strip()], "webSearchUsed": bool(analysis.get("webSearchUsed"))}}
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
