from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ..v1.history_report import CancellationRequested, VehicleHistoryClient, VehicleHistoryReport
from ..v1.otomoto_vehicle_identity import OtomotoVehicleIdentity
from ._service_common import REPORT_MISSING_FIRST_REGISTRATION, REPORT_MISSING_REGISTRATION, REPORT_MISSING_REGISTRATION_AND_DATE, REPORT_STATUS_CANCELLED, REPORT_STATUS_FAILED, REPORT_STATUS_NEEDS_INPUT, REPORT_STATUS_RUNNING, REPORT_STATUS_SUCCESS, REPORT_UPSTREAM_404, VehicleReportNeedsInput, utc_now
from ._service_json import _write_json
from ._service_listing_helpers import _normalize_lookup_identifier, _report_lookup_options


class ServiceReportLookupRuntimeMixin:
    def _write_cancelling_report_status(self, status_path: Path, status: dict[str, Any], listing: dict[str, Any], request_id: str) -> dict[str, Any]:
        lookup = status.get("lookup") if isinstance(status.get("lookup"), dict) else {}
        identity = self._read_identity_from_status(status)
        registration_number = lookup.get("registrationNumber")
        self._write_vehicle_report_status(
            status_path,
            {
                "status": "cancelling",
                "error": "Vehicle report lookup cancellation requested.",
                "progress_message": "Cancelling vehicle report lookup...",
                "identity": identity,
                "lookup": lookup or None,
                "lookup_options": _report_lookup_options({"vin": lookup.get("vin") or (identity.vin if identity else None), "registration_number": registration_number or (identity.registration_number if identity else None), "first_registration_date": identity.first_registration_date if identity else None, "reason": REPORT_UPSTREAM_404, "error": "Vehicle report lookup cancellation requested.", "date_from": (lookup.get("dateRange") or {}).get("from"), "date_to": (lookup.get("dateRange") or {}).get("to")}) if registration_number or identity is not None else None,
            },
        )
        return self._build_vehicle_report_state_payload(request_id, listing)

    def _write_vehicle_report_status(self, path: Path, status_data: dict[str, Any] | None = None, **legacy_kwargs: Any) -> None:
        status_payload = status_data or {}
        if legacy_kwargs:
            status_payload = {
                "status": legacy_kwargs.get("status"),
                "error": legacy_kwargs.get("error"),
                "retrieved_at": legacy_kwargs.get("retrieved_at", legacy_kwargs.get("retrieved_at") or legacy_kwargs.get("retrievedAt")),
                "progress_message": legacy_kwargs.get("progress_message", legacy_kwargs.get("progress_message") or legacy_kwargs.get("progressMessage")),
                "identity": legacy_kwargs.get("identity"),
                "lookup": legacy_kwargs.get("lookup"),
                "lookup_options": legacy_kwargs.get("lookup_options", legacy_kwargs.get("lookup_options") or legacy_kwargs.get("lookupOptions")),
            }
        _write_json(path, {"status": status_payload["status"], "lastAttemptAt": utc_now(), "lastError": status_payload.get("error"), "retrievedAt": status_payload.get("retrieved_at"), "progressMessage": status_payload.get("progress_message"), "identity": self._serialize_identity(status_payload.get("identity")) if status_payload.get("identity") is not None else None, "lookup": status_payload.get("lookup"), "lookupOptions": status_payload.get("lookup_options")})

    def _serialize_identity(self, identity: OtomotoVehicleIdentity | dict[str, Any] | None) -> dict[str, Any]:
        if identity is None:
            return {}
        if isinstance(identity, dict):
            return {"advertId": identity.get("advertId"), "vin": identity.get("vin"), "registrationNumber": identity.get("registrationNumber"), "firstRegistrationDate": identity.get("firstRegistrationDate")}
        return {"advertId": identity.advert_id, "vin": identity.vin, "registrationNumber": identity.registration_number, "firstRegistrationDate": identity.first_registration_date}

    def _read_identity_from_status(self, status: dict[str, Any]) -> OtomotoVehicleIdentity | None:
        identity = status.get("identity")
        if not isinstance(identity, dict) or not isinstance(identity.get("vin"), str) or not identity.get("vin") or not isinstance(identity.get("advertId"), str) or not identity.get("advertId"):
            return None
        return OtomotoVehicleIdentity(advert_id=identity["advertId"], encrypted_vin=None, encrypted_first_registration_date=None, encrypted_registration_number=None, vin=_normalize_lookup_identifier(identity["vin"], label="VIN"), first_registration_date=identity.get("firstRegistrationDate"), registration_number=_normalize_lookup_identifier(identity["registrationNumber"], label="Registration number") if isinstance(identity.get("registrationNumber"), str) and identity.get("registrationNumber") else None)

    def _fetch_listing_identity(self, url: str) -> OtomotoVehicleIdentity:
        from . import service as service_module

        return service_module.fetch_otomoto_vehicle_identity(url, timeout_s=float(self.parser_options.get("request_timeout_s", 45.0)))

    def _fetch_history_report(self, status_path: Path, identity: OtomotoVehicleIdentity) -> VehicleHistoryReport:
        try:
            return VehicleHistoryClient(timeout_s=float(self.parser_options.get("request_timeout_s", 45.0)), retry_attempts=int(self.parser_options.get("retry_attempts", 4)), backoff_base_s=float(self.parser_options.get("backoff_base", 1.0))).fetch_report(identity.registration_number, identity.vin, identity.first_registration_date)
        except RuntimeError as exc:
            if "HTTP 404" not in str(exc):
                raise
            lookup_options = _report_lookup_options({"vin": identity.vin, "registration_number": identity.registration_number, "first_registration_date": identity.first_registration_date, "reason": REPORT_UPSTREAM_404, "error": f"Could not find a report for {identity.first_registration_date}. Try another date."})
            self._write_vehicle_report_status(status_path, {"status": REPORT_STATUS_NEEDS_INPUT, "error": lookup_options["error"], "identity": identity, "lookup_options": lookup_options, "lookup": {"registrationNumber": identity.registration_number}})
            raise VehicleReportNeedsInput(str(exc)) from exc

    def _ensure_identity_ready_for_report(self, status_path: Path, identity: OtomotoVehicleIdentity) -> None:
        if identity.registration_number and identity.first_registration_date:
            return
        reason = REPORT_MISSING_REGISTRATION_AND_DATE if not identity.registration_number and not identity.first_registration_date else REPORT_MISSING_REGISTRATION if not identity.registration_number else REPORT_MISSING_FIRST_REGISTRATION
        lookup_options = _report_lookup_options({"vin": identity.vin, "registration_number": identity.registration_number, "first_registration_date": identity.first_registration_date, "reason": reason, "error": "Provide the missing registration details to search for the report."})
        self._write_vehicle_report_status(status_path, {"status": REPORT_STATUS_NEEDS_INPUT, "error": lookup_options["error"], "identity": identity, "lookup_options": lookup_options})
        raise VehicleReportNeedsInput(lookup_options["error"])

    def _start_vehicle_report_lookup_job(self, lookup_job: dict[str, Any]) -> None:
        future_key = (lookup_job["request_id"], lookup_job["listing_id"])
        with self._lock:
            existing = self._report_futures.get(future_key)
            if existing is not None and not existing.done():
                return
            cancel_event = __import__("threading").Event()
            self._report_cancel_events[future_key] = cancel_event
            self._report_futures[future_key] = self.executor.submit(self._run_vehicle_report_lookup, {**lookup_job, "cancel_event": cancel_event})

    def _run_vehicle_report_lookup(self, lookup_job: dict[str, Any]) -> None:
        status_path = self._vehicle_report_status_path(lookup_job["request_id"], lookup_job["listing_id"])
        cache_path = self._vehicle_report_path(lookup_job["request_id"], lookup_job["listing_id"])
        history_client = VehicleHistoryClient(timeout_s=float(self.parser_options.get("request_timeout_s", 45.0)), retry_attempts=int(self.parser_options.get("retry_attempts", 4)), backoff_base_s=float(self.parser_options.get("backoff_base", 1.0)), cancel_event=lookup_job["cancel_event"])
        start, end = date.fromisoformat(lookup_job["date_from"]), date.fromisoformat(lookup_job["date_to"])
        try:
            history_client.bootstrap_session()
            for offset in range(max(0, (end - start).days + 1)):
                candidate_date = (start + timedelta(days=offset)).isoformat()
                if lookup_job["cancel_event"].is_set():
                    return self._write_cancelled_vehicle_report_status(status_path, lookup_job)
                self._write_vehicle_report_status(status_path, {"status": REPORT_STATUS_RUNNING, "identity": lookup_job["identity"], "progress_message": f"Checking {candidate_date} ({offset + 1}/{(end - start).days + 1})...", "lookup": {"registrationNumber": lookup_job["registration_number"], "vin": lookup_job["identity"].vin, "dateRange": {"from": lookup_job["date_from"], "to": lookup_job["date_to"]}, "currentDate": candidate_date}})
                try:
                    history = history_client.fetch_report(lookup_job["registration_number"], lookup_job["identity"].vin, candidate_date)
                except CancellationRequested:
                    return self._write_cancelled_vehicle_report_status(status_path, lookup_job)
                except RuntimeError as exc:
                    if lookup_job["cancel_event"].is_set():
                        return self._write_cancelled_vehicle_report_status(status_path, lookup_job)
                    if "HTTP 404" in str(exc):
                        continue
                    self._write_vehicle_report_status(status_path, {"status": REPORT_STATUS_FAILED, "error": f"Could not fetch vehicle report data: {exc}", "identity": lookup_job["identity"], "lookup": {"registrationNumber": lookup_job["registration_number"], "vin": lookup_job["identity"].vin, "dateRange": {"from": lookup_job["date_from"], "to": lookup_job["date_to"]}}})
                    return
                payload = self._build_vehicle_report_payload(lookup_job["listing"], OtomotoVehicleIdentity(advert_id=lookup_job["identity"].advert_id, encrypted_vin=None, encrypted_first_registration_date=None, encrypted_registration_number=None, vin=lookup_job["identity"].vin, first_registration_date=candidate_date, registration_number=lookup_job["registration_number"]), history)
                _write_json(cache_path, payload)
                self._write_vehicle_report_status(status_path, {"status": REPORT_STATUS_SUCCESS, "retrieved_at": payload["retrievedAt"], "identity": payload["identity"], "lookup": {"registrationNumber": lookup_job["registration_number"], "vin": lookup_job["identity"].vin, "dateRange": {"from": lookup_job["date_from"], "to": lookup_job["date_to"]}, "currentDate": candidate_date}})
                return
            lookup_options = _report_lookup_options({"vin": lookup_job["identity"].vin, "registration_number": lookup_job["registration_number"], "first_registration_date": None, "reason": REPORT_UPSTREAM_404, "error": "No report was found in that date range. Try another date range.", "date_from": lookup_job["date_from"], "date_to": lookup_job["date_to"]})
            self._write_vehicle_report_status(status_path, {"status": REPORT_STATUS_NEEDS_INPUT, "error": lookup_options["error"], "identity": OtomotoVehicleIdentity(advert_id=lookup_job["identity"].advert_id, encrypted_vin=None, encrypted_first_registration_date=None, encrypted_registration_number=None, vin=lookup_job["identity"].vin, first_registration_date=None, registration_number=lookup_job["registration_number"]), "lookup": {"registrationNumber": lookup_job["registration_number"], "vin": lookup_job["identity"].vin, "dateRange": {"from": lookup_job["date_from"], "to": lookup_job["date_to"]}}, "lookup_options": lookup_options})
        except CancellationRequested:
            self._write_cancelled_vehicle_report_status(status_path, lookup_job)
        except Exception as exc:
            self._write_vehicle_report_status(status_path, {"status": REPORT_STATUS_FAILED, "error": f"Vehicle report lookup stopped unexpectedly: {exc}", "identity": lookup_job["identity"], "lookup": {"registrationNumber": lookup_job["registration_number"], "vin": lookup_job["identity"].vin, "dateRange": {"from": lookup_job["date_from"], "to": lookup_job["date_to"]}}, "lookup_options": _report_lookup_options({"vin": lookup_job["identity"].vin, "registration_number": lookup_job["registration_number"], "first_registration_date": None, "reason": REPORT_UPSTREAM_404, "error": f"Vehicle report lookup stopped unexpectedly: {exc}", "date_from": lookup_job["date_from"], "date_to": lookup_job["date_to"]})})
        finally:
            with self._lock:
                self._report_futures.pop((lookup_job["request_id"], lookup_job["listing_id"]), None)
                self._report_cancel_events.pop((lookup_job["request_id"], lookup_job["listing_id"]), None)

    def _write_cancelled_vehicle_report_status(self, status_path: Path, lookup_job: dict[str, Any] | None = None, **legacy_kwargs: Any) -> None:
        job = lookup_job or {
            "identity": legacy_kwargs["identity"],
            "registration_number": legacy_kwargs["registration_number"],
            "date_from": legacy_kwargs["date_from"],
            "date_to": legacy_kwargs["date_to"],
        }
        self._write_vehicle_report_status(status_path, {"status": REPORT_STATUS_CANCELLED, "error": "Vehicle report lookup was cancelled.", "identity": job["identity"], "lookup": {"registrationNumber": job["registration_number"], "vin": job["identity"].vin, "dateRange": {"from": job["date_from"], "to": job["date_to"]}}, "lookup_options": _report_lookup_options({"vin": job["identity"].vin, "registration_number": job["registration_number"], "first_registration_date": job["identity"].first_registration_date, "reason": REPORT_UPSTREAM_404, "error": "Vehicle report lookup was cancelled.", "date_from": job["date_from"], "date_to": job["date_to"]})})
