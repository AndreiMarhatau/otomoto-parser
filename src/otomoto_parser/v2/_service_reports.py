from __future__ import annotations

from pathlib import Path
from typing import Any

from ..v1.otomoto_vehicle_identity import OtomotoVehicleIdentity
from ._service_common import (
    REPORT_PROGRESS_FETCHING_IDENTITY,
    REPORT_PROGRESS_FETCHING_REPORT,
    REPORT_STATUS_CANCELLED,
    REPORT_STATUS_CANCELLING,
    REPORT_STATUS_FAILED,
    REPORT_STATUS_NEEDS_INPUT,
    REPORT_STATUS_RUNNING,
    REPORT_STATUS_SUCCESS,
    TERMINAL_REPORT_STATUSES,
    VehicleReportNeedsInput,
)
from ._service_json import _read_json, _write_json
from ._service_listing_helpers import _normalize_lookup_date, _normalize_lookup_identifier


class ServiceReportMixin:
    def get_vehicle_report(self, request_id: str, listing_id: str, *, force_refresh: bool = False) -> dict[str, Any]:
        with self._request_lock(request_id):
            listing = self._resolve_listing_for_report(request_id, listing_id)
            canonical_listing_id = listing["id"]
            status_path = self._vehicle_report_status_path(request_id, canonical_listing_id)
            cache_path = self._vehicle_report_path(request_id, canonical_listing_id)
            status = _read_json(status_path, {})
            if not force_refresh:
                return self._cached_or_status_payload(request_id, listing, cache_path, status)
            self._ensure_report_refresh_allowed(request_id, canonical_listing_id, status)
            return self._refresh_vehicle_report(
                request_id,
                listing,
                {"canonical_listing_id": canonical_listing_id, "status_path": status_path, "cache_path": cache_path},
            )

    def submit_vehicle_report_lookup(self, request_id: str, listing_id: str, lookup_input: dict[str, str]) -> dict[str, Any]:
        with self._request_lock(request_id):
            listing = self._resolve_listing_for_report(request_id, listing_id)
            future_key = (request_id, listing["id"])
            with self._lock:
                active_future = self._report_futures.get(future_key)
                if active_future is not None and not active_future.done():
                    status = _read_json(self._vehicle_report_status_path(request_id, listing["id"]), {})
                    return self._build_vehicle_report_state_payload(request_id, listing, status=status)
            identity = self._lookup_identity(request_id, listing)
            normalized_vin = _normalize_lookup_identifier(identity.vin, label="VIN")
            normalized_from = _normalize_lookup_date(lookup_input["date_from"])
            normalized_to = _normalize_lookup_date(lookup_input["date_to"])
            if normalized_from > normalized_to:
                raise RuntimeError("Start date cannot be later than end date.")
            normalized_registration = _normalize_lookup_identifier(lookup_input["registration_number"], label="Registration number")
            return self._submit_lookup_job(
                request_id,
                listing,
                {
                    "identity": identity,
                    "normalized_vin": normalized_vin,
                    "normalized_registration": normalized_registration,
                    "normalized_from": normalized_from,
                    "normalized_to": normalized_to,
                },
            )

    def cancel_vehicle_report_lookup(self, request_id: str, listing_id: str) -> dict[str, Any]:
        with self._request_lock(request_id):
            listing = self._resolve_listing_for_report(request_id, listing_id)
            canonical_listing_id = listing["id"]
            status_path = self._vehicle_report_status_path(request_id, canonical_listing_id)
            status = _read_json(status_path, {})
            future_key = (request_id, canonical_listing_id)
            with self._lock:
                active_future = self._report_futures.get(future_key)
                cancel_event = self._report_cancel_events.get(future_key)
                if active_future is None or active_future.done() or cancel_event is None:
                    raise RuntimeError("No active vehicle report lookup is currently running for this listing.")
            cached = _read_json(self._vehicle_report_path(request_id, canonical_listing_id), None)
            latest_status = _read_json(status_path, {})
            if cached is not None or latest_status.get("status") in TERMINAL_REPORT_STATUSES:
                return self._build_vehicle_report_state_payload(request_id, listing, status=latest_status)
            payload = self._write_cancelling_report_status(status_path, status, listing, request_id)
            cancel_event.set()
            final_status = _read_json(status_path, {})
            if final_status.get("status") in TERMINAL_REPORT_STATUSES:
                return self._build_vehicle_report_state_payload(request_id, listing, status=final_status)
            return payload

    def _cached_or_status_payload(self, request_id: str, listing: dict[str, Any], cache_path: Path, status: dict[str, Any]) -> dict[str, Any]:
        cached = _read_json(cache_path, None)
        if cached is not None:
            return cached
        if status.get("status") in {REPORT_STATUS_RUNNING, REPORT_STATUS_CANCELLING, REPORT_STATUS_NEEDS_INPUT, REPORT_STATUS_CANCELLED}:
            return self._build_vehicle_report_state_payload(request_id, listing, status=status)
        if status.get("status") == REPORT_STATUS_FAILED and (status.get("lookup") is not None or status.get("lookupOptions") is not None):
            return self._build_vehicle_report_state_payload(request_id, listing, status=status)
        return self._refresh_vehicle_report(
            request_id,
            listing,
            {"canonical_listing_id": listing["id"], "status_path": self._vehicle_report_status_path(request_id, listing["id"]), "cache_path": cache_path},
        )

    def _ensure_report_refresh_allowed(self, request_id: str, canonical_listing_id: str, status: dict[str, Any]) -> None:
        future_key = (request_id, canonical_listing_id)
        with self._lock:
            active_future = self._report_futures.get(future_key)
            report_lookup_running = active_future is not None and not active_future.done()
        if report_lookup_running or status.get("status") in {REPORT_STATUS_RUNNING, REPORT_STATUS_CANCELLING}:
            raise RuntimeError("A vehicle report lookup is already running for this listing.")
        if self._has_active_analysis_for_listing(request_id, canonical_listing_id):
            raise RuntimeError("Cannot regenerate the vehicle report while red-flag analysis is still running for this listing.")

    def _refresh_vehicle_report(self, request_id: str, listing: dict[str, Any], report_paths: dict[str, Any]) -> dict[str, Any]:
        url = listing.get("url")
        if not isinstance(url, str) or not url:
            self._write_vehicle_report_status(report_paths["status_path"], {"status": "failed", "error": "Listing URL is missing, so the vehicle report cannot be fetched."})
            raise RuntimeError("Listing URL is missing, so the vehicle report cannot be fetched.")
        try:
            self._write_vehicle_report_status(report_paths["status_path"], {"status": REPORT_STATUS_RUNNING, "progress_message": REPORT_PROGRESS_FETCHING_IDENTITY})
            identity = self._fetch_listing_identity(url)
            self._ensure_identity_ready_for_report(report_paths["status_path"], identity)
            self._write_vehicle_report_status(report_paths["status_path"], {"status": REPORT_STATUS_RUNNING, "progress_message": REPORT_PROGRESS_FETCHING_REPORT, "identity": identity})
            history = self._fetch_history_report(report_paths["status_path"], identity)
        except VehicleReportNeedsInput:
            return self._build_vehicle_report_state_payload(request_id, listing)
        except Exception as exc:
            error_message = f"Could not fetch vehicle report data: {exc}"
            self._write_vehicle_report_status(report_paths["status_path"], {"status": REPORT_STATUS_FAILED, "error": error_message})
            raise RuntimeError(error_message) from exc
        payload = self._build_vehicle_report_payload(listing, identity, history)
        self.get_request(request_id)
        _write_json(report_paths["cache_path"], payload)
        self._write_vehicle_report_status(report_paths["status_path"], {"status": REPORT_STATUS_SUCCESS, "retrieved_at": payload["retrievedAt"], "identity": identity})
        return payload

    def _lookup_identity(self, request_id: str, listing: dict[str, Any]) -> OtomotoVehicleIdentity:
        status = _read_json(self._vehicle_report_status_path(request_id, listing["id"]), {})
        identity = self._read_identity_from_status(status)
        if identity is not None:
            return identity
        url = listing.get("url")
        if not isinstance(url, str) or not url:
            raise RuntimeError("Listing URL is missing, so the vehicle report cannot be fetched.")
        identity = self._fetch_listing_identity(url)
        if not identity.vin:
            raise RuntimeError("VIN is missing, so the vehicle report cannot be fetched.")
        return identity

    def _submit_lookup_job(self, request_id: str, listing: dict[str, Any], lookup_request: dict[str, Any]) -> dict[str, Any]:
        canonical_listing_id = listing["id"]
        status_path = self._vehicle_report_status_path(request_id, canonical_listing_id)
        cache_path = self._vehicle_report_path(request_id, canonical_listing_id)
        if cache_path.exists():
            cache_path.unlink()
        identity = lookup_request["identity"]
        normalized_identity = OtomotoVehicleIdentity(advert_id=identity.advert_id, encrypted_vin=None, encrypted_first_registration_date=identity.encrypted_first_registration_date, encrypted_registration_number=identity.encrypted_registration_number, vin=lookup_request["normalized_vin"], first_registration_date=identity.first_registration_date, registration_number=lookup_request["normalized_registration"])
        self._write_vehicle_report_status(
            status_path,
            {
                "status": REPORT_STATUS_RUNNING,
                "identity": normalized_identity,
                "progress_message": f"Searching reports from {lookup_request['normalized_from']} to {lookup_request['normalized_to']}...",
                "lookup": {"registrationNumber": lookup_request["normalized_registration"], "vin": lookup_request["normalized_vin"], "dateRange": {"from": lookup_request["normalized_from"], "to": lookup_request["normalized_to"]}},
            },
        )
        self._start_vehicle_report_lookup_job(
            {
                "request_id": request_id,
                "listing_id": canonical_listing_id,
                "listing": listing,
                "identity": normalized_identity,
                "registration_number": lookup_request["normalized_registration"],
                "date_from": lookup_request["normalized_from"],
                "date_to": lookup_request["normalized_to"],
            }
        )
        return self._build_vehicle_report_state_payload(request_id, listing)
