from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..v1.history_report import VehicleHistoryReport
from ..v1.otomoto_vehicle_identity import OtomotoVehicleIdentity
from ._service_common import REPORT_STATUS_IDLE, REPORT_STATUS_NEEDS_INPUT, REPORT_UPSTREAM_404, utc_now
from ._service_json import _build_report_snapshot_id, _read_json, _write_json
from ._service_listing_helpers import _location_display


class ServiceReportRuntimeMixin:
    def _build_vehicle_report_payload(self, listing: dict[str, Any], identity: OtomotoVehicleIdentity, history: VehicleHistoryReport) -> dict[str, Any]:
        payload = {"listingId": listing["id"], "listingUrl": listing.get("url"), "listingTitle": listing.get("title"), "retrievedAt": utc_now(), "identity": {"advertId": identity.advert_id, "vin": identity.vin, "registrationNumber": identity.registration_number, "firstRegistrationDate": identity.first_registration_date}, "report": asdict(history), "summary": self._build_report_summary(history)}
        payload["reportSnapshotId"] = _build_report_snapshot_id(payload)
        return payload

    def _build_vehicle_report_state_payload(self, request_id: str, listing: dict[str, Any], *, status: dict[str, Any] | None = None) -> dict[str, Any]:
        current_status = status or _read_json(self._vehicle_report_status_path(request_id, str(listing["id"])), {})
        cached = _read_json(self._vehicle_report_path(request_id, str(listing["id"])), None)
        return cached if cached is not None else {"listingId": listing["id"], "listingUrl": listing.get("url"), "listingTitle": listing.get("title"), "retrievedAt": current_status.get("retrievedAt"), "lastAttemptAt": current_status.get("lastAttemptAt"), "status": current_status.get("status") or REPORT_STATUS_IDLE, "progressMessage": current_status.get("progressMessage"), "error": current_status.get("lastError"), "identity": current_status.get("identity") or {}, "lookup": current_status.get("lookup"), "lookupOptions": current_status.get("lookupOptions")}

    def _vehicle_report_path(self, request_id: str, listing_id: str) -> Path:
        return self.request_paths(request_id).reports_dir / f"{__import__('hashlib').sha256(listing_id.encode('utf-8')).hexdigest()}.json"

    def _vehicle_report_status_path(self, request_id: str, listing_id: str) -> Path:
        return self.request_paths(request_id).reports_dir / f"{__import__('hashlib').sha256(f'{listing_id}:status'.encode('utf-8')).hexdigest()}.json"

    def _write_json_recovered_report_status(self, path: Path, previous_status: dict[str, Any]) -> None:
        previous_lookup = previous_status.get("lookup") if isinstance(previous_status.get("lookup"), dict) else {}
        previous_identity = previous_status.get("identity") if isinstance(previous_status.get("identity"), dict) else {}
        previous_options = previous_status.get("lookupOptions") if isinstance(previous_status.get("lookupOptions"), dict) else {}
        recovered_options = {"reason": previous_options.get("reason") or REPORT_UPSTREAM_404, "vin": previous_options.get("vin") or previous_identity.get("vin"), "registrationNumber": previous_options.get("registrationNumber") or previous_lookup.get("registrationNumber") or previous_identity.get("registrationNumber"), "firstRegistrationDate": previous_options.get("firstRegistrationDate") or previous_identity.get("firstRegistrationDate"), "dateRange": {"from": ((previous_options.get("dateRange") or {}).get("from")) or ((previous_lookup.get("dateRange") or {}).get("from")), "to": ((previous_options.get("dateRange") or {}).get("to")) or ((previous_lookup.get("dateRange") or {}).get("to"))}, "error": "The previous vehicle report lookup was interrupted. Please try again."}
        _write_json(path, {"status": REPORT_STATUS_NEEDS_INPUT, "lastAttemptAt": utc_now(), "lastError": recovered_options["error"], "retrievedAt": previous_status.get("retrievedAt"), "progressMessage": None, "identity": previous_status.get("identity"), "lookup": previous_status.get("lookup"), "lookupOptions": recovered_options})

    def _canonical_listing_id(self, record: dict[str, Any]) -> str:
        node = record.get("node") if isinstance(record.get("node"), dict) else {}
        return str(record.get("item_id") or node.get("id") or record.get("item_key") or "")

    def _find_listing_record(self, request_id: str, listing_id: str) -> dict[str, Any]:
        results_path = Path(self.get_request(request_id)["resultsPath"])
        if not results_path.exists():
            raise RuntimeError("The stored results for this request are not available.")
        needle = str(listing_id)
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = __import__("json").loads(line)
                candidates = {str(record.get("item_id") or ""), str(record.get("item_key") or ""), str(((record.get("node") or {}).get("id")) or "")}
                if needle in candidates:
                    return record
        raise KeyError(listing_id)

    def _resolve_listing_for_report(self, request_id: str, listing_id: str) -> dict[str, Any]:
        request = self.get_request(request_id)
        if request["resultsReady"]:
            categories = _read_json(Path(request["categorizedPath"]), {}).get("categories", {})
            if isinstance(categories, dict):
                for category in categories.values():
                    for item in category.get("items", []) if isinstance(category, dict) else []:
                        if isinstance(item, dict) and str(item.get("id")) == str(listing_id):
                            return item
        record = self._find_listing_record(request_id, listing_id)
        node = record.get("node") if isinstance(record.get("node"), dict) else {}
        return {"id": self._canonical_listing_id(record), "title": node.get("title"), "url": node.get("url"), "location": _location_display(node.get("location"))}

    def _build_report_summary(self, history: VehicleHistoryReport) -> dict[str, Any]:
        technical_data = history.technical_data.get("technicalData", {})
        basic_data = technical_data.get("basicData", {}) if isinstance(technical_data, dict) else {}
        ownership_history = technical_data.get("ownershipHistory", {}) if isinstance(technical_data, dict) else {}
        autodna_unavailable = isinstance(history.autodna_data, dict) and history.autodna_data.get("unavailable") is True
        carfax_unavailable = isinstance(history.carfax_data, dict) and history.carfax_data.get("unavailable") is True
        return {"make": basic_data.get("make"), "model": basic_data.get("model"), "variant": basic_data.get("type"), "modelYear": basic_data.get("modelYear"), "fuelType": basic_data.get("fuel"), "engineCapacity": basic_data.get("engineCapacity"), "enginePower": basic_data.get("enginePower"), "bodyType": basic_data.get("bodyType"), "color": basic_data.get("color"), "ownersCount": ownership_history.get("numberOfOwners"), "coOwnersCount": ownership_history.get("numberOfCoowners"), "lastOwnershipChange": ownership_history.get("dateOfLastOwnershipChange"), "autodnaAvailable": bool(history.autodna_data) and not autodna_unavailable, "carfaxAvailable": bool(history.carfax_data) and not carfax_unavailable, "autodnaUnavailable": autodna_unavailable, "carfaxUnavailable": carfax_unavailable}

    def _attach_report_cache_metadata(self, request_id: str, items: list[dict[str, Any]]) -> None:
        for item in items:
            if isinstance(item, dict) and item.get("id") is not None:
                status = _read_json(self._vehicle_report_status_path(request_id, str(item["id"])), {})
                report = _read_json(self._vehicle_report_path(request_id, str(item["id"])), None)
                item["vehicleReport"] = {"cached": report is not None, "retrievedAt": report.get("retrievedAt") if report else None, "status": status.get("status"), "lastAttemptAt": status.get("lastAttemptAt"), "lastError": status.get("lastError"), "progressMessage": status.get("progressMessage"), "lookup": status.get("lookup"), "lookupOptions": status.get("lookupOptions")}
