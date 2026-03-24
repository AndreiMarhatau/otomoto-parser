from __future__ import annotations

import json
import threading
import time
from concurrent.futures import Future
from pathlib import Path
from typing import Any
from urllib.error import URLError

from fastapi.testclient import TestClient

from otomoto_parser.v1.parser import RUN_MODE_APPEND_NEWER, RUN_MODE_FULL, RUN_MODE_RESUME
from otomoto_parser.v2 import app as app_module
from otomoto_parser.v2 import service as service_module
from otomoto_parser.v2.app import create_app
from otomoto_parser.v2.service import (
    CATEGORY_DATA_NOT_VERIFIED,
    CATEGORY_FAVORITES,
    CATEGORY_IMPORTED_FROM_US,
    CATEGORY_PRICE_OUT_OF_RANGE,
    CATEGORY_TO_BE_CHECKED,
    ParserAppService,
    build_categorized_payload,
)
from otomoto_parser.v1.history_report import VehicleHistoryReport
from otomoto_parser.v1.otomoto_vehicle_identity import OtomotoVehicleIdentity


def _record(
    item_id: str,
    *,
    price_evaluation: dict | None,
    cepik_verified: bool,
    country_origin: str | None,
    title: str,
) -> dict:
    parameters = [
        {"key": "make", "displayValue": "Toyota", "value": "toyota"},
        {"key": "model", "displayValue": "Avensis", "value": "avensis"},
        {"key": "body_type", "displayValue": "Kombi", "value": "combi"},
        {"key": "year", "displayValue": "2014", "value": "2014"},
        {"key": "mileage", "displayValue": "150917 km", "value": "150917"},
        {"key": "engine_capacity", "displayValue": "1987 cm3", "value": "1987"},
        {"key": "engine_power", "displayValue": "152 KM", "value": "152"},
        {"key": "fuel_type", "displayValue": "Benzyna", "value": "petrol"},
        {"key": "gearbox", "displayValue": "Automatyczna", "value": "automatic"},
    ]
    if country_origin is not None:
        parameters.append(
            {
                "key": "country_origin",
                "displayValue": country_origin.upper(),
                "value": country_origin,
            }
        )

    node = {
        "id": item_id,
        "title": title,
        "createdAt": "2026-03-12T13:08:23Z",
        "shortDescription": "Short description",
        "url": f"https://www.otomoto.pl/osobowe/oferta/{item_id}.html",
        "thumbnail": {"x1": "https://example.com/car.jpg", "x2": "https://example.com/car@2x.jpg"},
        "parameters": parameters,
        "location": {"city": {"name": "Warsaw"}, "region": {"name": "Mazowieckie"}},
        "price": {"amount": {"units": 43000, "currencyCode": "PLN"}},
        "cepikVerified": cepik_verified,
        "priceEvaluation": price_evaluation,
    }
    return {
        "search_url": "https://example.com/search",
        "page_url": "https://example.com/search?page=1",
        "page_number": 1,
        "item_index": 0,
        "item_id": item_id,
        "item_key": f"id:{item_id}",
        "node": node,
        "edge": {"node": node},
    }


def _sample_records() -> list[dict]:
    return [
        _record("1", price_evaluation=None, cepik_verified=True, country_origin="pl", title="Price out of range"),
        _record("2", price_evaluation={"indicator": "IN"}, cepik_verified=False, country_origin="pl", title="Not verified"),
        _record("3", price_evaluation={"indicator": "IN"}, cepik_verified=True, country_origin="us", title="Imported from US"),
        _record("4", price_evaluation={"indicator": "IN"}, cepik_verified=True, country_origin="pl", title="To check"),
    ]


def _fake_identity() -> OtomotoVehicleIdentity:
    return OtomotoVehicleIdentity(
        advert_id="6146171299",
        encrypted_vin="encrypted-vin",
        encrypted_first_registration_date="encrypted-date",
        encrypted_registration_number="encrypted-reg",
        vin="WDDSJ4EB2EN056917",
        first_registration_date="2014-01-01",
        registration_number="DLU8613F",
    )


def _fake_identity_unformatted() -> OtomotoVehicleIdentity:
    return OtomotoVehicleIdentity(
        advert_id="6146171299",
        encrypted_vin="encrypted-vin",
        encrypted_first_registration_date="encrypted-date",
        encrypted_registration_number="encrypted-reg",
        vin="wdd sj4eb2 en056917",
        first_registration_date="2014-01-01",
        registration_number="dlu 8613f",
    )


def _fake_identity_missing_first_registration() -> OtomotoVehicleIdentity:
    return OtomotoVehicleIdentity(
        advert_id="6146171299",
        encrypted_vin="encrypted-vin",
        encrypted_first_registration_date=None,
        encrypted_registration_number="encrypted-reg",
        vin="WDDSJ4EB2EN056917",
        first_registration_date=None,
        registration_number="DLU8613F",
    )


def _fake_identity_missing_registration_and_first_registration() -> OtomotoVehicleIdentity:
    return OtomotoVehicleIdentity(
        advert_id="6146171299",
        encrypted_vin="encrypted-vin",
        encrypted_first_registration_date=None,
        encrypted_registration_number=None,
        vin="WDDSJ4EB2EN056917",
        first_registration_date=None,
        registration_number=None,
    )


def _fake_identity_missing_registration() -> OtomotoVehicleIdentity:
    return OtomotoVehicleIdentity(
        advert_id="6146171299",
        encrypted_vin="encrypted-vin",
        encrypted_first_registration_date="encrypted-date",
        encrypted_registration_number=None,
        vin="WDDSJ4EB2EN056917",
        first_registration_date="2014-01-01",
        registration_number=None,
    )


def _fake_history_report() -> VehicleHistoryReport:
    return VehicleHistoryReport(
        registration_number="DLU8613F",
        vin_number="WDDSJ4EB2EN056917",
        first_registration_date="2014-01-01",
        api_version="1.0.20",
        technical_data={
            "technicalData": {
                "basicData": {
                    "make": "Mercedes-Benz",
                    "model": "CLA",
                    "type": "250",
                    "modelYear": "2014",
                    "fuel": "Petrol",
                    "engineCapacity": "1991",
                    "enginePower": "211",
                    "bodyType": "Sedan",
                    "color": "White",
                },
                "ownershipHistory": {
                    "numberOfOwners": 2,
                    "numberOfCoowners": 0,
                    "dateOfLastOwnershipChange": "2021-06-04",
                },
            }
        },
        autodna_data={"summary": {"events": 3}},
        carfax_data={"summary": {"entries": 1}},
        timeline_data={"timelineData": {"events": [{"type": "registration"}]}},
    )


def _fake_listing_page(*_: object, **__: object) -> dict[str, Any]:
    return {
        "id": "6146171299",
        "title": "Mercedes-Benz CLA 250",
        "sellerLink": "https://example.com/dealer",
        "description": "Detailed listing page payload",
        "parametersDict": {
            "vin": {"values": [{"value": "encrypted-vin"}]},
            "registration": {"values": [{"value": "encrypted-reg"}]},
        },
    }


def _fake_red_flag_analyzer(_: str, model_input: dict[str, Any], cancel_event: threading.Event) -> dict[str, Any]:
    assert model_input["searchResultRaw"]["item_id"] == "4"
    assert model_input["listingPageRaw"]["title"] == "Mercedes-Benz CLA 250"
    assert model_input["vehicleReport"] is not None
    if cancel_event.is_set():
        raise service_module.CancellationRequested("cancelled")
    return {
        "summary": "Serious issues detected.",
        "redFlags": [
            "VIN appears in U.S. import context and should be checked for damage history.",
            "Vehicle history sources show multiple external datasets, which merits manual verification.",
        ],
        "warnings": [
            "The listing omits enough provenance detail that import paperwork should be reviewed manually.",
        ],
        "greenFlags": [
            "The listing page, search result, and vehicle report align on the core vehicle identity.",
        ],
        "webSearchUsed": True,
    }


def _blocking_red_flag_analyzer(_: str, model_input: dict[str, Any], cancel_event: threading.Event) -> dict[str, Any]:
    del model_input
    if cancel_event.wait(5):
        raise service_module.CancellationRequested("cancelled")
    return {"summary": "late", "redFlags": [], "warnings": [], "greenFlags": [], "webSearchUsed": False}


def _slow_success_red_flag_analyzer(_: str, model_input: dict[str, Any], cancel_event: threading.Event) -> dict[str, Any]:
    del model_input
    if cancel_event.wait(1):
        raise service_module.CancellationRequested("cancelled")
    return {"summary": "Completed", "redFlags": [], "warnings": [], "greenFlags": [], "webSearchUsed": False}


def _slow_cancel_red_flag_analyzer(_: str, model_input: dict[str, Any], cancel_event: threading.Event) -> dict[str, Any]:
    del model_input
    if cancel_event.wait(5):
        time.sleep(0.5)
        raise service_module.CancellationRequested("cancelled")
    return {"summary": "Completed", "redFlags": [], "warnings": [], "greenFlags": [], "webSearchUsed": False}


def _fake_red_flag_analyzer_without_report(_: str, model_input: dict[str, Any], cancel_event: threading.Event) -> dict[str, Any]:
    assert model_input["vehicleReport"] is None
    assert model_input["reportSnapshotId"] == "missing"
    if cancel_event.is_set():
        raise service_module.CancellationRequested("cancelled")
    return {
        "summary": "Ran without report.",
        "redFlags": ["No report was available during analysis."],
        "warnings": ["The analysis had to rely on the listing alone because no vehicle report was cached."],
        "greenFlags": [],
        "webSearchUsed": False,
    }


class FakeParserRunner:
    def __init__(self) -> None:
        self.append_counter = 0

    def __call__(
        self,
        start_url: str,
        output_path: Path,
        state_path: Path,
        *,
        run_mode: str,
        progress_callback=None,
        **_: object,
    ) -> None:
        records = list(_sample_records())
        if run_mode == RUN_MODE_APPEND_NEWER:
            self.append_counter += 1
            records.append(
                _record(
                    f"new-{self.append_counter}",
                    price_evaluation={"indicator": "IN"},
                    cepik_verified=True,
                    country_origin="pl",
                    title=f"Fresh listing {self.append_counter}",
                )
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if run_mode == RUN_MODE_FULL or not output_path.exists():
            existing: list[str] = []
        else:
            existing = output_path.read_text(encoding="utf-8").splitlines()

        if progress_callback is not None:
            progress_callback({"event": "page_fetch_started", "page": 1, "pages_completed": 0, "results_written": len(existing)})

        lines = [json.dumps(record, ensure_ascii=True) for record in records]
        if existing and run_mode == RUN_MODE_APPEND_NEWER:
            output_path.write_text("\n".join(existing + lines) + "\n", encoding="utf-8")
            total_results = len(existing) + len(lines)
        else:
            output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            total_results = len(lines)

        state_path.write_text(json.dumps({"next_page": 2}), encoding="utf-8")

        if progress_callback is not None:
            progress_callback(
                {
                    "event": "page_fetch_finished",
                    "page": 1,
                    "written": len(lines),
                    "state": {
                        "start_url": start_url,
                        "next_page": 2,
                        "pages_completed": 1,
                        "results_written": total_results,
                        "has_more": False,
                    },
                }
            )
            progress_callback(
                {
                    "event": "complete",
                    "state": {
                        "start_url": start_url,
                        "next_page": 2,
                        "pages_completed": 1,
                        "results_written": total_results,
                        "has_more": False,
                    },
                }
            )


class FailOnSecondRunParserRunner(FakeParserRunner):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0
        self.modes: list[str] = []

    def __call__(self, *args, **kwargs) -> None:
        self.calls += 1
        self.modes.append(kwargs["run_mode"])
        if self.calls == 1:
            return super().__call__(*args, **kwargs)
        raise RuntimeError("simulated rerun failure")


class FullRerunDropsListingRunner(FakeParserRunner):
    def __init__(self) -> None:
        super().__init__()
        self.full_calls = 0

    def __call__(self, start_url: str, output_path: Path, state_path: Path, *, run_mode: str, progress_callback=None, **kwargs: object) -> None:
        if run_mode == RUN_MODE_FULL:
            self.full_calls += 1
            if self.full_calls > 1:
                records = [record for record in _sample_records() if record["item_id"] != "4"]
                output_path.parent.mkdir(parents=True, exist_ok=True)
                lines = [json.dumps(record, ensure_ascii=True) for record in records]
                output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                state_path.write_text(json.dumps({"next_page": 2}), encoding="utf-8")
                if progress_callback is not None:
                    progress_callback({"event": "page_fetch_started", "page": 1, "pages_completed": 0, "results_written": 0})
                    progress_callback(
                        {
                            "event": "page_fetch_finished",
                            "page": 1,
                            "written": len(lines),
                            "state": {
                                "start_url": start_url,
                                "next_page": 2,
                                "pages_completed": 1,
                                "results_written": len(lines),
                                "has_more": False,
                            },
                        }
                    )
                    progress_callback(
                        {
                            "event": "complete",
                            "state": {
                                "start_url": start_url,
                                "next_page": 2,
                                "pages_completed": 1,
                                "results_written": len(lines),
                                "has_more": False,
                            },
                        }
                    )
                return
        return super().__call__(
            start_url,
            output_path,
            state_path,
            run_mode=run_mode,
            progress_callback=progress_callback,
            **kwargs,
        )


class FailingThenResumeParserRunner(FakeParserRunner):
    def __init__(self) -> None:
        super().__init__()
        self.modes: list[str] = []

    def __call__(self, start_url: str, output_path: Path, state_path: Path, *, run_mode: str, progress_callback=None, **kwargs) -> None:
        self.modes.append(run_mode)
        if len(self.modes) == 1:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps(
                    {
                        "start_url": start_url,
                        "next_page": 2,
                        "pages_completed": 1,
                        "results_written": 2,
                        "has_more": True,
                    }
                ),
                encoding="utf-8",
            )
            raise RuntimeError("initial run failed")
        return super().__call__(start_url, output_path, state_path, run_mode=run_mode, progress_callback=progress_callback, **kwargs)


class SuccessFailResumeParserRunner(FakeParserRunner):
    def __init__(self) -> None:
        super().__init__()
        self.modes: list[str] = []

    def __call__(self, start_url: str, output_path: Path, state_path: Path, *, run_mode: str, progress_callback=None, **kwargs) -> None:
        self.modes.append(run_mode)
        if len(self.modes) == 2:
            state_path.write_text(
                json.dumps(
                    {
                        "start_url": start_url,
                        "next_page": 3,
                        "pages_completed": 2,
                        "results_written": 5,
                        "has_more": True,
                    }
                ),
                encoding="utf-8",
            )
            raise RuntimeError("redo failed")
        return super().__call__(start_url, output_path, state_path, run_mode=run_mode, progress_callback=progress_callback, **kwargs)


class AppendFailureThenResumeParserRunner(FakeParserRunner):
    def __init__(self) -> None:
        super().__init__()
        self.modes: list[str] = []

    def __call__(self, start_url: str, output_path: Path, state_path: Path, *, run_mode: str, progress_callback=None, **kwargs) -> None:
        self.modes.append(run_mode)
        if len(self.modes) == 2:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps(
                    {
                        "start_url": start_url,
                        "next_page": 3,
                        "pages_completed": 2,
                        "results_written": 6,
                        "has_more": True,
                    }
                ),
                encoding="utf-8",
            )
            raise RuntimeError("append-newer failed mid-run")
        return super().__call__(start_url, output_path, state_path, run_mode=run_mode, progress_callback=progress_callback, **kwargs)


class EmptyResultsParserRunner:
    def __call__(self, start_url: str, output_path: Path, state_path: Path, *, run_mode: str, progress_callback=None, **kwargs) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("", encoding="utf-8")
        state_path.write_text(
            json.dumps(
                {
                    "start_url": start_url,
                    "next_page": 1,
                    "pages_completed": 1,
                    "results_written": 0,
                    "has_more": False,
                }
            ),
            encoding="utf-8",
        )
        if progress_callback is not None:
            progress_callback({"event": "page_fetch_started", "page": 1, "pages_completed": 0, "results_written": 0})
            progress_callback(
                {
                    "event": "page_fetch_finished",
                    "page": 1,
                    "written": 0,
                    "state": {
                        "start_url": start_url,
                        "next_page": 1,
                        "pages_completed": 1,
                        "results_written": 0,
                        "has_more": False,
                    },
                }
            )
            progress_callback(
                {
                    "event": "complete",
                    "state": {
                        "start_url": start_url,
                        "next_page": 1,
                        "pages_completed": 1,
                        "results_written": 0,
                        "has_more": False,
                    },
                }
            )


def _wait_until_ready(client: TestClient, request_id: str) -> dict:
    deadline = time.time() + 10
    while time.time() < deadline:
        response = client.get(f"/api/requests/{request_id}")
        response.raise_for_status()
        item = response.json()["item"]
        if item["status"] in {"ready", "failed"}:
            return item
        time.sleep(0.05)
    raise AssertionError("request did not finish")


def _wait_for_vehicle_report_state(client: TestClient, request_id: str, listing_id: str, *, timeout_s: float = 10.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        response = client.get(f"/api/requests/{request_id}/listings/{listing_id}/vehicle-report")
        response.raise_for_status()
        item = response.json()["item"]
        if item.get("report") is not None or item.get("status") in {"needs_input", "failed"}:
            return item
        time.sleep(0.05)
    raise AssertionError("vehicle report lookup did not finish")


def _wait_for_vehicle_report_status(
    client: TestClient,
    request_id: str,
    listing_id: str,
    expected_status: str,
    *,
    timeout_s: float = 10.0,
) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        response = client.get(f"/api/requests/{request_id}/listings/{listing_id}/vehicle-report")
        response.raise_for_status()
        item = response.json()["item"]
        if item.get("status") == expected_status:
            return item
        time.sleep(0.05)
    raise AssertionError(f"vehicle report lookup did not reach status {expected_status}")


def _wait_for_red_flag_status(
    client: TestClient,
    request_id: str,
    listing_id: str,
    expected_status: str,
    *,
    timeout_s: float = 10.0,
) -> dict:
    deadline = time.time() + timeout_s
    last_item = None
    while time.time() < deadline:
        response = client.get(f"/api/requests/{request_id}/listings/{listing_id}/red-flags")
        response.raise_for_status()
        item = response.json()["item"]
        last_item = item
        if item.get("status") == expected_status:
            return item
        time.sleep(0.05)
    raise AssertionError(f"red-flag analysis did not reach status {expected_status}; last item: {last_item}")


def _wait_for_red_flag_progress(
    client: TestClient,
    request_id: str,
    listing_id: str,
    expected_progress: str,
    *,
    timeout_s: float = 10.0,
) -> dict:
    deadline = time.time() + timeout_s
    last_item = None
    while time.time() < deadline:
        response = client.get(f"/api/requests/{request_id}/listings/{listing_id}/red-flags")
        response.raise_for_status()
        item = response.json()["item"]
        last_item = item
        if item.get("status") == "running" and item.get("progressMessage") == expected_progress:
            return item
        time.sleep(0.05)
    raise AssertionError(f"red-flag analysis did not reach progress {expected_progress}; last item: {last_item}")


def _wait_for_red_flag_rerun_start(client: TestClient, request_id: str, listing_id: str, *, timeout_s: float = 10.0):
    deadline = time.time() + timeout_s
    last_response = None
    while time.time() < deadline:
        response = client.post(f"/api/requests/{request_id}/listings/{listing_id}/red-flags")
        last_response = response
        if response.status_code == 200:
            return response
        time.sleep(0.05)
    detail = None
    if last_response is not None:
        try:
            detail = last_response.json()
        except Exception:  # noqa: BLE001
            detail = last_response.text
    raise AssertionError(f"red-flag analysis rerun did not start; last response: {detail}")


def test_build_categorized_payload_assigns_expected_categories(tmp_path: Path) -> None:
    results_path = tmp_path / "results.jsonl"
    results_path.write_text(
        "".join(f"{json.dumps(record, ensure_ascii=True)}\n" for record in _sample_records()),
        encoding="utf-8",
    )

    payload = build_categorized_payload(results_path)

    assert payload["totalCount"] == 4
    assert payload["categories"][CATEGORY_PRICE_OUT_OF_RANGE]["count"] == 1
    assert payload["categories"][CATEGORY_DATA_NOT_VERIFIED]["count"] == 1
    assert payload["categories"][CATEGORY_IMPORTED_FROM_US]["count"] == 1
    assert payload["categories"][CATEGORY_TO_BE_CHECKED]["count"] == 1
    assert list(payload["categories"]) == [
        CATEGORY_PRICE_OUT_OF_RANGE,
        CATEGORY_IMPORTED_FROM_US,
        CATEGORY_DATA_NOT_VERIFIED,
        CATEGORY_TO_BE_CHECKED,
    ]


def test_us_origin_takes_precedence_over_unverified(tmp_path: Path) -> None:
    record = _record(
        "us-and-unverified",
        price_evaluation={"indicator": "IN"},
        cepik_verified=False,
        country_origin="us",
        title="US import and unverified",
    )

    results_path = tmp_path / "results.jsonl"
    results_path.write_text(f"{json.dumps(record, ensure_ascii=True)}\n", encoding="utf-8")

    payload = build_categorized_payload(results_path)
    assert payload["categories"][CATEGORY_IMPORTED_FROM_US]["count"] == 1
    assert payload["categories"][CATEGORY_DATA_NOT_VERIFIED]["count"] == 0


def test_price_out_of_range_takes_precedence_over_us_origin_and_unverified(tmp_path: Path) -> None:
    record = _record(
        "out-of-range-us-unverified",
        price_evaluation=None,
        cepik_verified=False,
        country_origin="us",
        title="Out of range, US import, and unverified",
    )

    results_path = tmp_path / "results.jsonl"
    results_path.write_text(f"{json.dumps(record, ensure_ascii=True)}\n", encoding="utf-8")

    payload = build_categorized_payload(results_path)
    assert payload["categories"][CATEGORY_PRICE_OUT_OF_RANGE]["count"] == 1
    assert payload["categories"][CATEGORY_IMPORTED_FROM_US]["count"] == 0
    assert payload["categories"][CATEGORY_DATA_NOT_VERIFIED]["count"] == 0


def test_missing_cepik_verified_falls_back_to_to_be_checked(tmp_path: Path) -> None:
    record = _record(
        "missing-cepik",
        price_evaluation={"indicator": "IN"},
        cepik_verified=True,
        country_origin="pl",
        title="Missing CEPiK",
    )
    del record["node"]["cepikVerified"]
    record["edge"]["node"] = record["node"]

    results_path = tmp_path / "results.jsonl"
    results_path.write_text(f"{json.dumps(record, ensure_ascii=True)}\n", encoding="utf-8")

    payload = build_categorized_payload(results_path)
    assert payload["categories"][CATEGORY_TO_BE_CHECKED]["count"] == 1
    assert payload["categories"][CATEGORY_DATA_NOT_VERIFIED]["count"] == 0


def test_legacy_price_shape_is_used_for_result_cards(tmp_path: Path) -> None:
    record = _record(
        "legacy-price",
        price_evaluation={"indicator": "IN"},
        cepik_verified=True,
        country_origin="pl",
        title="Legacy price",
    )
    record["node"]["price"] = {"value": 40123, "currency": "PLN"}
    record["edge"]["node"] = record["node"]

    results_path = tmp_path / "results.jsonl"
    results_path.write_text(f"{json.dumps(record, ensure_ascii=True)}\n", encoding="utf-8")

    payload = build_categorized_payload(results_path)
    item = payload["categories"][CATEGORY_TO_BE_CHECKED]["items"][0]
    assert item["price"] == 40123
    assert item["priceCurrency"] == "PLN"


def test_usa_origin_is_classified_as_imported_from_us(tmp_path: Path) -> None:
    record = _record(
        "usa-origin",
        price_evaluation={"indicator": "IN"},
        cepik_verified=True,
        country_origin="usa",
        title="USA origin",
    )

    results_path = tmp_path / "results.jsonl"
    results_path.write_text(f"{json.dumps(record, ensure_ascii=True)}\n", encoding="utf-8")

    payload = build_categorized_payload(results_path)
    assert payload["categories"][CATEGORY_IMPORTED_FROM_US]["count"] == 1


def test_none_price_evaluation_is_classified_as_out_of_range(tmp_path: Path) -> None:
    record = _record(
        "none-price-eval",
        price_evaluation={"indicator": "NONE"},
        cepik_verified=True,
        country_origin="pl",
        title="No price evaluation",
    )

    results_path = tmp_path / "results.jsonl"
    results_path.write_text(f"{json.dumps(record, ensure_ascii=True)}\n", encoding="utf-8")

    payload = build_categorized_payload(results_path)
    assert payload["categories"][CATEGORY_PRICE_OUT_OF_RANGE]["count"] == 1


def test_api_request_lifecycle(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        assert create_response.status_code == 201
        request_id = create_response.json()["item"]["id"]

        ready_item = _wait_until_ready(client, request_id)
        assert ready_item["status"] == "ready"
        assert ready_item["resultsWritten"] == 4
        assert ready_item["excelReady"] is True

        results_response = client.get(f"/api/requests/{request_id}/results")
        assert results_response.status_code == 200
        results_payload = results_response.json()
        assert results_payload["categories"][CATEGORY_TO_BE_CHECKED]["count"] == 1

        excel_response = client.get(f"/api/requests/{request_id}/excel")
        assert excel_response.status_code == 200
        assert excel_response.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        resume_response = client.post(f"/api/requests/{request_id}/resume")
        assert resume_response.status_code == 200
        resumed_item = _wait_until_ready(client, request_id)
        assert resumed_item["resultsWritten"] == 9

        redo_response = client.post(f"/api/requests/{request_id}/redo")
        assert redo_response.status_code == 200
        redone_item = _wait_until_ready(client, request_id)
        assert redone_item["resultsWritten"] == 4


def test_unknown_api_route_keeps_404_when_frontend_bundle_exists(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        response = client.get("/api/does-not-exist")
        assert response.status_code == 404
        base_response = client.get("/api")
        assert base_response.status_code == 404


def test_failed_rerun_keeps_previous_results_available(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FailOnSecondRunParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        ready_item = _wait_until_ready(client, request_id)
        assert ready_item["resultsReady"] is True
        assert ready_item["excelReady"] is True

        rerun_response = client.post(f"/api/requests/{request_id}/resume")
        assert rerun_response.status_code == 200

        failed_item = _wait_until_ready(client, request_id)
        assert failed_item["status"] == "failed"
        assert failed_item["resultsReady"] is True
        assert failed_item["excelReady"] is True
        assert service.parser_runner.modes == [RUN_MODE_FULL, RUN_MODE_APPEND_NEWER]

        results_response = client.get(f"/api/requests/{request_id}/results")
        assert results_response.status_code == 200
        excel_response = client.get(f"/api/requests/{request_id}/excel")
        assert excel_response.status_code == 200


def test_resume_endpoint_uses_true_resume_for_incomplete_requests(tmp_path: Path) -> None:
    runner = FailingThenResumeParserRunner()
    service = ParserAppService(tmp_path, parser_runner=runner, parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]

        failed_item = _wait_until_ready(client, request_id)
        assert failed_item["status"] == "failed"
        assert failed_item["resultsReady"] is False

        resume_response = client.post(f"/api/requests/{request_id}/resume")
        assert resume_response.status_code == 200

        resumed_item = _wait_until_ready(client, request_id)
        assert resumed_item["status"] == "ready"
        assert runner.modes == [RUN_MODE_FULL, RUN_MODE_RESUME]


def test_resume_after_failed_redo_uses_resume_mode(tmp_path: Path) -> None:
    runner = SuccessFailResumeParserRunner()
    service = ParserAppService(tmp_path, parser_runner=runner, parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        ready_item = _wait_until_ready(client, request_id)
        assert ready_item["status"] == "ready"

        redo_response = client.post(f"/api/requests/{request_id}/redo")
        assert redo_response.status_code == 200
        failed_item = _wait_until_ready(client, request_id)
        assert failed_item["status"] == "failed"
        assert failed_item["resultsReady"] is False

        resume_response = client.post(f"/api/requests/{request_id}/resume")
        assert resume_response.status_code == 200
        resumed_item = _wait_until_ready(client, request_id)
        assert resumed_item["status"] == "ready"
        assert runner.modes == [RUN_MODE_FULL, RUN_MODE_FULL, RUN_MODE_RESUME]


def test_resume_after_interrupted_append_newer_uses_resume_mode(tmp_path: Path) -> None:
    runner = AppendFailureThenResumeParserRunner()
    service = ParserAppService(tmp_path, parser_runner=runner, parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        ready_item = _wait_until_ready(client, request_id)
        assert ready_item["status"] == "ready"

        refresh_response = client.post(f"/api/requests/{request_id}/resume")
        assert refresh_response.status_code == 200
        failed_item = _wait_until_ready(client, request_id)
        assert failed_item["status"] == "failed"
        assert failed_item["resultsReady"] is True

        retry_response = client.post(f"/api/requests/{request_id}/resume")
        assert retry_response.status_code == 200
        resumed_item = _wait_until_ready(client, request_id)
        assert resumed_item["status"] == "ready"
        assert runner.modes == [RUN_MODE_FULL, RUN_MODE_APPEND_NEWER, RUN_MODE_RESUME]


def test_empty_result_search_is_treated_as_ready(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=EmptyResultsParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]

        ready_item = _wait_until_ready(client, request_id)
        assert ready_item["status"] == "ready"
        assert ready_item["resultsWritten"] == 0

        results_response = client.get(f"/api/requests/{request_id}/results")
        assert results_response.status_code == 200
        assert results_response.json()["totalCount"] == 0


def test_geocode_endpoint_returns_server_side_lookup(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)
    monkeypatch.setattr(
        app_module,
        "geocode_location",
        lambda query: {"lat": 52.23, "lon": 21.01, "label": f"Resolved {query}"},
    )

    with TestClient(app) as client:
        response = client.get("/api/geocode", params={"query": "Warsaw"})
        assert response.status_code == 200
        assert response.json()["item"]["label"] == "Resolved Warsaw"


def test_geocode_batch_endpoint_returns_items(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)
    monkeypatch.setattr(
        app_module,
        "geocode_location",
        lambda query: {"lat": 52.23, "lon": 21.01, "label": f"Resolved {query}"},
    )

    with TestClient(app) as client:
        response = client.post("/api/geocode/batch", json={"queries": ["Warsaw", "Krakow"]})
        assert response.status_code == 200
        assert response.json()["items"]["Warsaw"]["label"] == "Resolved Warsaw"


def test_delete_request_endpoint_removes_request(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        delete_response = client.delete(f"/api/requests/{request_id}")
        assert delete_response.status_code == 204

        detail_response = client.get(f"/api/requests/{request_id}")
        assert detail_response.status_code == 404


def test_vehicle_report_endpoint_fetches_and_caches_report(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)
    identity_calls: list[str] = []
    history_calls: list[tuple[str, str, str]] = []

    monkeypatch.setattr(
        service_module,
        "fetch_otomoto_vehicle_identity",
        lambda url, **kwargs: identity_calls.append(url) or _fake_identity(),
    )

    def fake_fetch_report(self, registration_number: str, vin_number: str, first_registration_date: str) -> VehicleHistoryReport:
        history_calls.append((registration_number, vin_number, first_registration_date))
        return _fake_history_report()

    monkeypatch.setattr(service_module.VehicleHistoryClient, "fetch_report", fake_fetch_report)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        first_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert first_response.status_code == 200
        assert first_response.json()["item"]["identity"]["vin"] == "WDDSJ4EB2EN056917"
        assert len(identity_calls) == 1
        assert history_calls == [("DLU8613F", "WDDSJ4EB2EN056917", "2014-01-01")]

        second_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert second_response.status_code == 200
        assert len(identity_calls) == 1
        assert len(history_calls) == 1

        results_response = client.get(
            f"/api/requests/{request_id}/results",
            params={"category": CATEGORY_TO_BE_CHECKED},
        )
        payload = results_response.json()
        assert payload["currentCategory"] == CATEGORY_TO_BE_CHECKED
        item = payload["items"][0]
        assert item["vehicleReport"]["cached"] is True
        assert item["vehicleReport"]["retrievedAt"]


def test_settings_endpoint_reports_environment_key_and_stores_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-test-key-1234")
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        response = client.get("/api/settings")
        assert response.status_code == 200
        assert response.json()["item"] == {
            "openaiApiKeyConfigured": True,
            "openaiApiKeySource": "environment",
            "openaiApiKeyMasked": "env-...1234",
            "openaiApiKeyStored": False,
        }

        update = client.put("/api/settings", json={"openaiApiKey": "stored-test-key-9999"})
        assert update.status_code == 200
        assert update.json()["item"]["openaiApiKeySource"] == "stored"
        assert update.json()["item"]["openaiApiKeyMasked"] == "stor...9999"
        assert update.json()["item"]["openaiApiKeyStored"] is True


def test_red_flag_analysis_endpoint_runs_with_listing_page_report_and_web_search(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-test-key-1234")
    service = ParserAppService(
        tmp_path,
        parser_runner=FakeParserRunner(),
        listing_page_fetcher=_fake_listing_page,
        red_flag_analyzer=_fake_red_flag_analyzer,
        parser_options={},
    )
    app = create_app(data_dir=tmp_path, service=service)

    monkeypatch.setattr(
        service_module,
        "fetch_otomoto_vehicle_identity",
        lambda url, **kwargs: _fake_identity(),
    )
    monkeypatch.setattr(service_module.VehicleHistoryClient, "fetch_report", lambda self, *args: _fake_history_report())

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        report_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert report_response.status_code == 200
        assert report_response.json()["item"]["report"] is not None

        start_response = client.post(f"/api/requests/{request_id}/listings/4/red-flags")
        assert start_response.status_code == 200
        item = _wait_for_red_flag_status(client, request_id, "4", "success")
        assert item["analysis"]["summary"] == "Serious issues detected."
        assert len(item["analysis"]["redFlags"]) == 2
        assert item["analysis"]["warnings"] == [
            "The listing omits enough provenance detail that import paperwork should be reviewed manually.",
        ]
        assert item["analysis"]["greenFlags"] == [
            "The listing page, search result, and vehicle report align on the core vehicle identity.",
        ]
        assert item["analysis"]["webSearchUsed"] is True
        assert item["reportReady"] is True
        assert item["model"] == "gpt-5.4"


def test_red_flag_analysis_becomes_stale_after_report_is_fetched(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-test-key-1234")
    service = ParserAppService(
        tmp_path,
        parser_runner=FakeParserRunner(),
        listing_page_fetcher=_fake_listing_page,
        red_flag_analyzer=_fake_red_flag_analyzer_without_report,
        parser_options={},
    )
    app = create_app(data_dir=tmp_path, service=service)

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", lambda url, **kwargs: _fake_identity())
    monkeypatch.setattr(service_module.VehicleHistoryClient, "fetch_report", lambda self, *args: _fake_history_report())

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        start_response = client.post(f"/api/requests/{request_id}/listings/4/red-flags")
        assert start_response.status_code == 200
        item = _wait_for_red_flag_status(client, request_id, "4", "success")
        assert item["reportReady"] is False
        assert item["reportSnapshotId"] == "missing"
        assert item["analysis"]["warnings"] == [
            "The analysis had to rely on the listing alone because no vehicle report was cached.",
        ]
        assert item["analysis"]["greenFlags"] == []

        report_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert report_response.status_code == 200
        report_snapshot_id = report_response.json()["item"]["reportSnapshotId"]

        stale_response = client.get(f"/api/requests/{request_id}/listings/4/red-flags")
        assert stale_response.status_code == 200
        stale_item = stale_response.json()["item"]
        assert stale_item["status"] == "idle"
        assert stale_item["stale"] is True
        assert stale_item["analysis"] is None
        assert stale_item["reportSnapshotId"] == report_snapshot_id
        assert stale_item["analysisReportSnapshotId"] == "missing"
        assert stale_item["error"] == "Analysis is outdated because the vehicle report changed. Run it again."


def test_red_flag_analysis_becomes_stale_after_report_regeneration(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-test-key-1234")
    service = ParserAppService(
        tmp_path,
        parser_runner=FakeParserRunner(),
        listing_page_fetcher=_fake_listing_page,
        red_flag_analyzer=_fake_red_flag_analyzer,
        parser_options={},
    )
    app = create_app(data_dir=tmp_path, service=service)
    fetch_count = {"value": 0}

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", lambda url, **kwargs: _fake_identity())

    def fake_fetch_report(self, *args) -> VehicleHistoryReport:
        fetch_count["value"] += 1
        report = _fake_history_report()
        report.autodna_data = {"summary": {"events": fetch_count["value"]}}
        return report

    monkeypatch.setattr(service_module.VehicleHistoryClient, "fetch_report", fake_fetch_report)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        first_report = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report").json()["item"]
        first_snapshot = first_report["reportSnapshotId"]

        analysis_start = client.post(f"/api/requests/{request_id}/listings/4/red-flags")
        assert analysis_start.status_code == 200
        analysis_item = _wait_for_red_flag_status(client, request_id, "4", "success")
        assert analysis_item["reportSnapshotId"] == first_snapshot

        regenerated_report = client.post(f"/api/requests/{request_id}/listings/4/vehicle-report/regenerate").json()["item"]
        second_snapshot = regenerated_report["reportSnapshotId"]
        assert second_snapshot != first_snapshot

        stale_response = client.get(f"/api/requests/{request_id}/listings/4/red-flags")
        stale_item = stale_response.json()["item"]
        assert stale_item["status"] == "idle"
        assert stale_item["stale"] is True
        assert stale_item["analysis"] is None
        assert stale_item["reportSnapshotId"] == second_snapshot
        assert stale_item["analysisReportSnapshotId"] == first_snapshot
        assert stale_item["error"] == "Analysis is outdated because the vehicle report changed. Run it again."


def test_red_flag_analysis_normalizes_legacy_cached_analysis(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-test-key-1234")
    service = ParserAppService(
        tmp_path,
        parser_runner=FakeParserRunner(),
        listing_page_fetcher=_fake_listing_page,
        parser_options={},
    )
    app = create_app(data_dir=tmp_path, service=service)

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", lambda url, **kwargs: _fake_identity())
    monkeypatch.setattr(service_module.VehicleHistoryClient, "fetch_report", lambda self, *args: _fake_history_report())

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        report_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert report_response.status_code == 200
        report_snapshot_id = report_response.json()["item"]["reportSnapshotId"]

        service_module._write_json(
            service._red_flag_analysis_path(request_id, "4"),
            {
                "listingId": "4",
                "listingUrl": "https://www.otomoto.pl/osobowe/oferta/mercedes-benz-cla-ID6Gv7s7.html",
                "listingTitle": "Mercedes-Benz CLA 250",
                "retrievedAt": "2026-03-24T00:00:00Z",
                "status": "success",
                "error": None,
                "model": "gpt-5.4",
                "reportReady": True,
                "reportSnapshotId": report_snapshot_id,
                "apiKeyConfigured": True,
                "analysis": {
                    "summary": "Legacy cache payload.",
                    "redFlags": ["Existing serious issue."],
                    "webSearchUsed": True,
                },
            },
        )

        response = client.get(f"/api/requests/{request_id}/listings/4/red-flags")
        assert response.status_code == 200
        item = response.json()["item"]
        assert item["status"] == "success"
        assert item["analysis"]["summary"] == "Legacy cache payload."
        assert item["analysis"]["redFlags"] == ["Existing serious issue."]
        assert item["analysis"]["warnings"] == []
        assert item["analysis"]["greenFlags"] == []
        assert item["analysis"]["webSearchUsed"] is True


def test_red_flag_analysis_can_be_cancelled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-test-key-1234")
    service = ParserAppService(
        tmp_path,
        parser_runner=FakeParserRunner(),
        listing_page_fetcher=_fake_listing_page,
        red_flag_analyzer=_blocking_red_flag_analyzer,
        parser_options={},
    )
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        start_response = client.post(f"/api/requests/{request_id}/listings/4/red-flags")
        assert start_response.status_code == 200
        _wait_for_red_flag_progress(client, request_id, "4", "Running GPT-5.4 red-flag analysis...")

        cancel_response = client.post(f"/api/requests/{request_id}/listings/4/red-flags/cancel")
        assert cancel_response.status_code == 200
        cancel_item = cancel_response.json()["item"]
        assert cancel_item["status"] in {"cancelling", "cancelled"}
        current = client.get(f"/api/requests/{request_id}/listings/4/red-flags").json()["item"]
        assert current["status"] in {"cancelling", "cancelled"}
        assert current["analysis"] is None


def test_red_flag_analysis_can_rerun_after_cancel_finishes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-test-key-1234")
    service = ParserAppService(
        tmp_path,
        parser_runner=FakeParserRunner(),
        listing_page_fetcher=_fake_listing_page,
        red_flag_analyzer=_blocking_red_flag_analyzer,
        parser_options={},
    )
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)
        monkeypatch.setattr(
            service_module,
            "fetch_otomoto_vehicle_identity",
            lambda url, **kwargs: _fake_identity(),
        )
        monkeypatch.setattr(service_module.VehicleHistoryClient, "fetch_report", lambda self, *args: _fake_history_report())
        report_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert report_response.status_code == 200

        assert client.post(f"/api/requests/{request_id}/listings/4/red-flags").status_code == 200
        _wait_for_red_flag_progress(client, request_id, "4", "Running GPT-5.4 red-flag analysis...")
        cancel_response = client.post(f"/api/requests/{request_id}/listings/4/red-flags/cancel")
        assert cancel_response.status_code == 200
        service.red_flag_analyzer = _fake_red_flag_analyzer

        start_response = _wait_for_red_flag_rerun_start(client, request_id, "4")
        assert start_response.status_code == 200
        item = _wait_for_red_flag_status(client, request_id, "4", "success")
        assert item["analysis"]["summary"] == "Serious issues detected."
        assert item["analysis"]["warnings"] == [
            "The listing omits enough provenance detail that import paperwork should be reviewed manually.",
        ]


def test_red_flag_analysis_cannot_restart_while_previous_run_is_cancelling(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-test-key-1234")
    service = ParserAppService(
        tmp_path,
        parser_runner=FakeParserRunner(),
        listing_page_fetcher=_fake_listing_page,
        red_flag_analyzer=_slow_cancel_red_flag_analyzer,
        parser_options={},
    )
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        assert client.post(f"/api/requests/{request_id}/listings/4/red-flags").status_code == 200
        _wait_for_red_flag_progress(client, request_id, "4", "Running GPT-5.4 red-flag analysis...")

        cancel_response = client.post(f"/api/requests/{request_id}/listings/4/red-flags/cancel")
        assert cancel_response.status_code == 200
        assert cancel_response.json()["item"]["status"] == "cancelling"

        blocked_rerun = client.post(f"/api/requests/{request_id}/listings/4/red-flags")
        assert blocked_rerun.status_code == 409
        assert blocked_rerun.json()["detail"] == "Red-flag analysis cancellation is still in progress for this listing."


def test_delete_request_is_blocked_while_red_flag_analysis_is_running(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-test-key-1234")
    service = ParserAppService(
        tmp_path,
        parser_runner=FakeParserRunner(),
        listing_page_fetcher=_fake_listing_page,
        red_flag_analyzer=_slow_success_red_flag_analyzer,
        parser_options={},
    )
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        ready_item = _wait_until_ready(client, request_id)

        assert client.post(f"/api/requests/{request_id}/listings/4/red-flags").status_code == 200
        _wait_for_red_flag_progress(client, request_id, "4", "Running GPT-5.4 red-flag analysis...")

        delete_response = client.delete(f"/api/requests/{request_id}")
        assert delete_response.status_code == 409
        assert delete_response.json()["detail"] == "Cannot delete a request while a vehicle report lookup or red-flag analysis is still running."

        _wait_for_red_flag_status(client, request_id, "4", "success")

        delete_response = client.delete(f"/api/requests/{request_id}")
        assert delete_response.status_code == 204

        detail_response = client.get(f"/api/requests/{request_id}")
        assert detail_response.status_code == 404

        run_dir = Path(ready_item["runDir"])
        assert not run_dir.exists()


def test_vehicle_report_regenerate_is_blocked_while_red_flag_analysis_is_running(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-test-key-1234")
    service = ParserAppService(
        tmp_path,
        parser_runner=FakeParserRunner(),
        listing_page_fetcher=_fake_listing_page,
        red_flag_analyzer=_slow_success_red_flag_analyzer,
        parser_options={},
    )
    app = create_app(data_dir=tmp_path, service=service)

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", lambda url, **kwargs: _fake_identity())
    monkeypatch.setattr(service_module.VehicleHistoryClient, "fetch_report", lambda self, *args: _fake_history_report())

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        initial_report = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert initial_report.status_code == 200

        analysis_start = client.post(f"/api/requests/{request_id}/listings/4/red-flags")
        assert analysis_start.status_code == 200
        _wait_for_red_flag_progress(client, request_id, "4", "Running GPT-5.4 red-flag analysis...")

        regenerate_response = client.post(f"/api/requests/{request_id}/listings/4/vehicle-report/regenerate")
        assert regenerate_response.status_code == 502
        assert regenerate_response.json()["detail"] == "Cannot regenerate the vehicle report while red-flag analysis is still running for this listing."

        _wait_for_red_flag_status(client, request_id, "4", "success")

        regenerate_response = client.post(f"/api/requests/{request_id}/listings/4/vehicle-report/regenerate")
        assert regenerate_response.status_code == 200


def test_results_endpoint_returns_only_requested_page_for_selected_category(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    extra_records = [
        _record(
            f"extra-{index}",
            price_evaluation={"indicator": "IN"},
            cepik_verified=True,
            country_origin="pl",
            title=f"Extra {index}",
        )
        for index in range(20)
    ]

    original_sample_records = globals()["_sample_records"]

    def sample_records_with_extras() -> list[dict[str, Any]]:
        return original_sample_records() + extra_records

    globals()["_sample_records"] = sample_records_with_extras
    try:
        with TestClient(app) as client:
            create_response = client.post(
                "/api/requests",
                json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
            )
            request_id = create_response.json()["item"]["id"]
            _wait_until_ready(client, request_id)

            page_one = client.get(
                f"/api/requests/{request_id}/results",
                params={"category": CATEGORY_TO_BE_CHECKED, "page": 1, "page_size": 5},
            )
            assert page_one.status_code == 200
            page_one_payload = page_one.json()
            assert page_one_payload["currentCategory"] == CATEGORY_TO_BE_CHECKED
            assert page_one_payload["pagination"] == {
                "page": 1,
                "pageSize": 5,
                "totalPages": 5,
                "totalItems": 21,
            }
            assert len(page_one_payload["items"]) == 5
            assert [item["id"] for item in page_one_payload["items"]] == ["4", "extra-0", "extra-1", "extra-2", "extra-3"]
            assert "items" not in page_one_payload["categories"][CATEGORY_TO_BE_CHECKED]

            page_last = client.get(
                f"/api/requests/{request_id}/results",
                params={"category": CATEGORY_TO_BE_CHECKED, "page": 99, "page_size": 5},
            )
            assert page_last.status_code == 200
            page_last_payload = page_last.json()
            assert page_last_payload["pagination"] == {
                "page": 5,
                "pageSize": 5,
                "totalPages": 5,
                "totalItems": 21,
            }
            assert [item["id"] for item in page_last_payload["items"]] == ["extra-19"]
    finally:
        globals()["_sample_records"] = original_sample_records


def test_results_endpoint_exposes_imported_from_us_before_data_not_verified(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        response = client.get(f"/api/requests/{request_id}/results")
        assert response.status_code == 200
        payload = response.json()
        assert list(payload["categories"])[:4] == [
            CATEGORY_PRICE_OUT_OF_RANGE,
            CATEGORY_IMPORTED_FROM_US,
            CATEGORY_DATA_NOT_VERIFIED,
            CATEGORY_TO_BE_CHECKED,
        ]
        assert payload["currentCategory"] == CATEGORY_PRICE_OUT_OF_RANGE


def test_saved_categories_can_be_created_assigned_renamed_deleted_and_survive_redo(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        initial_results = client.get(f"/api/requests/{request_id}/results")
        assert initial_results.status_code == 200
        initial_payload = initial_results.json()
        assert initial_payload["categories"][CATEGORY_FAVORITES] == {
            "label": CATEGORY_FAVORITES,
            "count": 0,
            "kind": "saved",
            "editable": False,
            "deletable": False,
        }
        assert initial_payload["assignableCategories"][0]["key"] == CATEGORY_FAVORITES

        category_response = client.post(
            f"/api/requests/{request_id}/categories",
            json={"name": "Weekend shortlist"},
        )
        assert category_response.status_code == 201
        category_key = category_response.json()["item"]["key"]

        assign_response = client.put(
            f"/api/requests/{request_id}/listings/4/categories",
            json={"categoryIds": [CATEGORY_FAVORITES, category_key]},
        )
        assert assign_response.status_code == 200
        assert assign_response.json()["item"]["savedCategoryKeys"] == [CATEGORY_FAVORITES, category_key]

        favorites_results = client.get(
            f"/api/requests/{request_id}/results",
            params={"category": CATEGORY_FAVORITES},
        )
        assert favorites_results.status_code == 200
        favorites_payload = favorites_results.json()
        assert favorites_payload["currentCategory"] == CATEGORY_FAVORITES
        assert [item["id"] for item in favorites_payload["items"]] == ["4"]
        assert favorites_payload["items"][0]["savedCategoryKeys"] == [CATEGORY_FAVORITES, category_key]

        custom_results = client.get(
            f"/api/requests/{request_id}/results",
            params={"category": category_key},
        )
        assert custom_results.status_code == 200
        assert custom_results.json()["categories"][category_key]["count"] == 1
        assert [item["id"] for item in custom_results.json()["items"]] == ["4"]

        rename_response = client.patch(
            f"/api/requests/{request_id}/categories/{category_key}",
            json={"name": "Family picks"},
        )
        assert rename_response.status_code == 200
        assert rename_response.json()["item"]["label"] == "Family picks"

        renamed_results = client.get(
            f"/api/requests/{request_id}/results",
            params={"category": category_key},
        )
        assert renamed_results.json()["categories"][category_key]["label"] == "Family picks"

        redo_response = client.post(f"/api/requests/{request_id}/redo")
        assert redo_response.status_code == 200
        _wait_until_ready(client, request_id)

        persisted_results = client.get(
            f"/api/requests/{request_id}/results",
            params={"category": category_key},
        )
        assert persisted_results.status_code == 200
        assert [item["id"] for item in persisted_results.json()["items"]] == ["4"]

        delete_response = client.delete(f"/api/requests/{request_id}/categories/{category_key}")
        assert delete_response.status_code == 204

        after_delete = client.get(f"/api/requests/{request_id}/results")
        assert category_key not in after_delete.json()["categories"]
        assert after_delete.json()["categories"][CATEGORY_FAVORITES]["count"] == 1


def test_listing_category_assignment_waits_for_ready_results(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        service.store.update_request(request_id, resultsReady=False, status="running")

        response = client.put(
            f"/api/requests/{request_id}/listings/4/categories",
            json={"categoryIds": [CATEGORY_FAVORITES]},
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "Results are not ready yet."


def test_rename_category_preserves_request_not_found(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        response = client.patch(
            "/api/requests/missing-request/categories/custom:demo",
            json={"name": "Renamed"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Request not found."


def test_full_redo_removes_saved_category_assignments_for_missing_listings(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FullRerunDropsListingRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        category_response = client.post(
            f"/api/requests/{request_id}/categories",
            json={"name": "Needs revisit"},
        )
        category_key = category_response.json()["item"]["key"]

        assign_response = client.put(
            f"/api/requests/{request_id}/listings/4/categories",
            json={"categoryIds": [CATEGORY_FAVORITES, category_key]},
        )
        assert assign_response.status_code == 200

        redo_response = client.post(f"/api/requests/{request_id}/redo")
        assert redo_response.status_code == 200
        _wait_until_ready(client, request_id)

        favorites_results = client.get(
            f"/api/requests/{request_id}/results",
            params={"category": CATEGORY_FAVORITES},
        )
        assert favorites_results.status_code == 200
        assert favorites_results.json()["categories"][CATEGORY_FAVORITES]["count"] == 0
        assert favorites_results.json()["items"] == []

        custom_results = client.get(
            f"/api/requests/{request_id}/results",
            params={"category": category_key},
        )
        assert custom_results.status_code == 200
        assert custom_results.json()["categories"][category_key]["count"] == 0
        assert custom_results.json()["items"] == []


def test_vehicle_report_regenerate_overwrites_cache_and_survives_redo(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)
    fetch_count = {"value": 0}

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", lambda url, **kwargs: _fake_identity())

    def fake_fetch_report(self, registration_number: str, vin_number: str, first_registration_date: str) -> VehicleHistoryReport:
        fetch_count["value"] += 1
        report = _fake_history_report()
        report.autodna_data = {"summary": {"events": fetch_count["value"]}}
        return report

    monkeypatch.setattr(service_module.VehicleHistoryClient, "fetch_report", fake_fetch_report)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        first_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        first_payload = first_response.json()["item"]
        assert first_payload["report"]["autodna_data"]["summary"]["events"] == 1

        regenerated_response = client.post(f"/api/requests/{request_id}/listings/4/vehicle-report/regenerate")
        regenerated_payload = regenerated_response.json()["item"]
        assert regenerated_payload["report"]["autodna_data"]["summary"]["events"] == 2

        redo_response = client.post(f"/api/requests/{request_id}/redo")
        assert redo_response.status_code == 200
        _wait_until_ready(client, request_id)

        cached_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        cached_payload = cached_response.json()["item"]
        assert cached_payload["report"]["autodna_data"]["summary"]["events"] == 2
        assert fetch_count["value"] == 2


def test_vehicle_report_endpoint_requires_listing_to_exist_in_current_request(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", lambda url, **kwargs: _fake_identity())
    monkeypatch.setattr(service_module.VehicleHistoryClient, "fetch_report", lambda self, *args, **kwargs: _fake_history_report())

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        ready_item = _wait_until_ready(client, request_id)
        assert ready_item["status"] == "ready"

        first_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert first_response.status_code == 200

        results_path = Path(ready_item["resultsPath"])
        categorized_path = Path(ready_item["categorizedPath"])
        filtered_records = [record for record in _sample_records() if record["item_id"] != "4"]
        results_path.write_text("".join(f"{json.dumps(record, ensure_ascii=True)}\n" for record in filtered_records), encoding="utf-8")
        categorized_path.write_text(json.dumps(build_categorized_payload(results_path), ensure_ascii=True), encoding="utf-8")

        missing_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert missing_response.status_code == 404


def test_vehicle_report_endpoint_normalizes_upstream_failures(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)
    identity_calls = {"value": 0}

    def fail_identity(url, **kwargs):
        identity_calls["value"] += 1
        raise URLError("temporary failure")

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", fail_identity)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert response.status_code == 502
        assert "Could not fetch vehicle report data" in response.json()["detail"]
        assert identity_calls["value"] == 1

        results_response = client.get(
            f"/api/requests/{request_id}/results",
            params={"category": CATEGORY_TO_BE_CHECKED},
        )
        item = results_response.json()["items"][0]
        assert item["vehicleReport"]["cached"] is False
        assert item["vehicleReport"]["status"] == "failed"
        assert item["vehicleReport"]["lastAttemptAt"]
        assert "Could not fetch vehicle report data" in item["vehicleReport"]["lastError"]

        retry_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert retry_response.status_code == 502
        assert identity_calls["value"] == 2


def test_vehicle_report_missing_first_registration_returns_lookup_options(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", lambda url, **kwargs: _fake_identity_missing_first_registration())

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert response.status_code == 200
        item = response.json()["item"]
        assert item["status"] == "needs_input"
        assert item["identity"]["vin"] == "WDDSJ4EB2EN056917"
        assert item["identity"]["registrationNumber"] == "DLU8613F"
        assert item["identity"]["firstRegistrationDate"] is None
        assert item["lookupOptions"]["reason"] == "missing_first_registration"
        assert item["lookupOptions"]["dateRange"]["from"]
        assert item["lookupOptions"]["dateRange"]["to"]


def test_vehicle_report_missing_registration_and_first_registration_returns_empty_registration_lookup(
    monkeypatch,
    tmp_path: Path,
) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    monkeypatch.setattr(
        service_module,
        "fetch_otomoto_vehicle_identity",
        lambda url, **kwargs: _fake_identity_missing_registration_and_first_registration(),
    )

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert response.status_code == 200
        item = response.json()["item"]
        assert item["status"] == "needs_input"
        assert item["identity"]["vin"] == "WDDSJ4EB2EN056917"
        assert item["identity"]["registrationNumber"] is None
        assert item["identity"]["firstRegistrationDate"] is None
        assert item["lookupOptions"]["reason"] == "missing_registration_and_date"
        assert item["lookupOptions"]["registrationNumber"] is None


def test_vehicle_report_missing_registration_returns_lookup_options_with_correct_reason(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    monkeypatch.setattr(
        service_module,
        "fetch_otomoto_vehicle_identity",
        lambda url, **kwargs: _fake_identity_missing_registration(),
    )

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert response.status_code == 200
        item = response.json()["item"]
        assert item["status"] == "needs_input"
        assert item["identity"]["vin"] == "WDDSJ4EB2EN056917"
        assert item["identity"]["registrationNumber"] is None
        assert item["identity"]["firstRegistrationDate"] == "2014-01-01"
        assert item["lookupOptions"]["reason"] == "missing_registration"
        assert item["lookupOptions"]["registrationNumber"] is None


def test_vehicle_report_404_allows_async_lookup_and_persists_progress(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)
    fetch_calls: list[tuple[str, str, str]] = []

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", lambda url, **kwargs: _fake_identity())

    def fake_fetch_report(self, registration_number: str, vin_number: str, first_registration_date: str) -> VehicleHistoryReport:
        fetch_calls.append((registration_number, vin_number, first_registration_date))
        if first_registration_date == "2014-01-01":
            raise RuntimeError("HistoriaPojazdu vehicle-data failed with HTTP 404: Not Found")
        if first_registration_date == "2014-01-02":
            time.sleep(0.15)
            report = _fake_history_report()
            report.first_registration_date = first_registration_date
            return report
        raise RuntimeError("HistoriaPojazdu vehicle-data failed with HTTP 404: Not Found")

    monkeypatch.setattr(service_module.VehicleHistoryClient, "fetch_report", fake_fetch_report)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        initial_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert initial_response.status_code == 200
        initial_item = initial_response.json()["item"]
        assert initial_item["status"] == "needs_input"
        assert initial_item["lookupOptions"]["reason"] == "upstream_404"
        assert initial_item["identity"]["vin"] == "WDDSJ4EB2EN056917"

        lookup_response = client.post(
            f"/api/requests/{request_id}/listings/4/vehicle-report/lookup",
            json={
                "registrationNumber": "DLU8613F",
                "dateFrom": "2014-01-01",
                "dateTo": "2014-01-03",
            },
        )
        assert lookup_response.status_code == 200
        lookup_item = lookup_response.json()["item"]
        assert lookup_item["status"] == "running"
        assert lookup_item["lookup"]["dateRange"] == {"from": "2014-01-01", "to": "2014-01-03"}

        reopened_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert reopened_response.status_code == 200
        reopened_item = reopened_response.json()["item"]
        assert reopened_item["status"] in {"running", "success"}
        if reopened_item["status"] == "running":
            assert reopened_item["lookup"]["registrationNumber"] == "DLU8613F"
            assert reopened_item["lookup"]["dateRange"] == {"from": "2014-01-01", "to": "2014-01-03"}

        final_item = _wait_for_vehicle_report_state(client, request_id, "4")
        assert final_item["report"]["first_registration_date"] == "2014-01-02"
        assert ("DLU8613F", "WDDSJ4EB2EN056917", "2014-01-01") in fetch_calls
        assert ("DLU8613F", "WDDSJ4EB2EN056917", "2014-01-02") in fetch_calls

        results_response = client.get(
            f"/api/requests/{request_id}/results",
            params={"category": CATEGORY_TO_BE_CHECKED},
        )
        item = results_response.json()["items"][0]
        assert item["vehicleReport"]["status"] == "success"
        assert item["vehicleReport"]["retrievedAt"]


def test_vehicle_report_lookup_normalizes_manual_inputs_and_persists_normalized_values(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)
    fetch_calls: list[tuple[str, str, str]] = []

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", lambda url, **kwargs: _fake_identity_unformatted())

    def fake_fetch_report(self, registration_number: str, vin_number: str, first_registration_date: str) -> VehicleHistoryReport:
        fetch_calls.append((registration_number, vin_number, first_registration_date))
        report = _fake_history_report()
        report.registration_number = registration_number
        report.vin_number = vin_number
        report.first_registration_date = first_registration_date
        return report

    monkeypatch.setattr(service_module.VehicleHistoryClient, "fetch_report", fake_fetch_report)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        response = client.post(
            f"/api/requests/{request_id}/listings/4/vehicle-report/lookup",
            json={
                "registrationNumber": " dlu 8613f ",
                "dateFrom": "2014-01-01",
                "dateTo": "2014-01-01",
            },
        )
        assert response.status_code == 200

        final_item = _wait_for_vehicle_report_state(client, request_id, "4")
        assert final_item["identity"]["vin"] == "WDDSJ4EB2EN056917"
        assert final_item["identity"]["registrationNumber"] == "DLU8613F"
        assert final_item["report"]["vin_number"] == "WDDSJ4EB2EN056917"
        assert final_item["report"]["registration_number"] == "DLU8613F"
        assert fetch_calls == [("DLU8613F", "WDDSJ4EB2EN056917", "2014-01-01")]


def test_vehicle_report_lookup_bootstraps_historia_pojazdu_once_per_job(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)
    bootstrap_calls: list[int] = []
    bootstrap_context_ids: list[int] = []
    fetch_calls: list[tuple[str, str, str]] = []

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", lambda url, **kwargs: _fake_identity())

    def fake_bootstrap_session(self) -> object:
        bootstrap_calls.append(id(self))
        token = object()
        self._bootstrap_context = token
        return token

    def fake_fetch_report(self, registration_number: str, vin_number: str, first_registration_date: str) -> VehicleHistoryReport:
        fetch_calls.append((registration_number, vin_number, first_registration_date))
        bootstrap_context_ids.append(id(self._bootstrap_context))
        if first_registration_date in {"2014-01-01", "2014-01-02"}:
            raise RuntimeError("HistoriaPojazdu vehicle-data failed with HTTP 404: Not Found")
        report = _fake_history_report()
        report.first_registration_date = first_registration_date
        return report

    monkeypatch.setattr(service_module.VehicleHistoryClient, "bootstrap_session", fake_bootstrap_session)
    monkeypatch.setattr(service_module.VehicleHistoryClient, "fetch_report", fake_fetch_report)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        lookup_response = client.post(
            f"/api/requests/{request_id}/listings/4/vehicle-report/lookup",
            json={
                "registrationNumber": "DLU8613F",
                "dateFrom": "2014-01-01",
                "dateTo": "2014-01-03",
            },
        )
        assert lookup_response.status_code == 200

        final_item = _wait_for_vehicle_report_state(client, request_id, "4")
        assert final_item["report"]["first_registration_date"] == "2014-01-03"
        assert len(bootstrap_calls) == 1
        assert fetch_calls == [
            ("DLU8613F", "WDDSJ4EB2EN056917", "2014-01-01"),
            ("DLU8613F", "WDDSJ4EB2EN056917", "2014-01-02"),
            ("DLU8613F", "WDDSJ4EB2EN056917", "2014-01-03"),
        ]
        assert len(set(bootstrap_context_ids)) == 1


def test_vehicle_report_lookup_rejects_invalid_dates_with_retryable_client_error(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", lambda url, **kwargs: _fake_identity())
    monkeypatch.setattr(
        service_module.VehicleHistoryClient,
        "fetch_report",
        lambda self, registration_number, vin_number, first_registration_date: (_ for _ in ()).throw(
            RuntimeError("HistoriaPojazdu vehicle-data failed with HTTP 404: Not Found")
        ),
    )

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        initial_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert initial_response.status_code == 200
        assert initial_response.json()["item"]["status"] == "needs_input"

        lookup_response = client.post(
            f"/api/requests/{request_id}/listings/4/vehicle-report/lookup",
            json={
                "registrationNumber": "DLU8613F",
                "dateFrom": "",
                "dateTo": "2014-01-03",
            },
        )
        assert lookup_response.status_code == 409
        assert lookup_response.json()["detail"] == "Invalid date format. Use YYYY-MM-DD."


def test_vehicle_report_lookup_rejects_non_iso_like_dates(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", lambda url, **kwargs: _fake_identity())
    monkeypatch.setattr(
        service_module.VehicleHistoryClient,
        "fetch_report",
        lambda self, registration_number, vin_number, first_registration_date: (_ for _ in ()).throw(
            RuntimeError("HistoriaPojazdu vehicle-data failed with HTTP 404: Not Found")
        ),
    )

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        initial_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert initial_response.status_code == 200
        assert initial_response.json()["item"]["status"] == "needs_input"

        lookup_response = client.post(
            f"/api/requests/{request_id}/listings/4/vehicle-report/lookup",
            json={
                "registrationNumber": "DLU8613F",
                "dateFrom": "2014-1-3",
                "dateTo": "2014-01-03",
            },
        )
        assert lookup_response.status_code == 409
        assert lookup_response.json()["detail"] == "Invalid date format. Use YYYY-MM-DD."


def test_vehicle_report_duplicate_lookup_submission_keeps_original_running_state(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", lambda url, **kwargs: _fake_identity())

    def fake_fetch_report(self, registration_number: str, vin_number: str, first_registration_date: str) -> VehicleHistoryReport:
        if first_registration_date == "2014-01-01":
            raise RuntimeError("HistoriaPojazdu vehicle-data failed with HTTP 404: Not Found")
        time.sleep(0.25)
        if first_registration_date == "2014-01-02":
            report = _fake_history_report()
            report.first_registration_date = first_registration_date
            return report
        raise RuntimeError("HistoriaPojazdu vehicle-data failed with HTTP 404: Not Found")

    monkeypatch.setattr(service_module.VehicleHistoryClient, "fetch_report", fake_fetch_report)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        initial_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert initial_response.status_code == 200
        assert initial_response.json()["item"]["status"] == "needs_input"

        first_lookup = client.post(
            f"/api/requests/{request_id}/listings/4/vehicle-report/lookup",
            json={
                "registrationNumber": "DLU8613F",
                "dateFrom": "2014-01-01",
                "dateTo": "2014-01-03",
            },
        )
        assert first_lookup.status_code == 200
        assert first_lookup.json()["item"]["lookup"]["dateRange"] == {"from": "2014-01-01", "to": "2014-01-03"}

        second_lookup = client.post(
            f"/api/requests/{request_id}/listings/4/vehicle-report/lookup",
            json={
                "registrationNumber": "XYZ9999",
                "dateFrom": "2015-01-01",
                "dateTo": "2015-01-03",
            },
        )
        assert second_lookup.status_code == 200
        second_item = second_lookup.json()["item"]
        assert second_item["status"] == "running"
        assert second_item["lastAttemptAt"]
        assert second_item["lookup"]["registrationNumber"] == "DLU8613F"
        assert second_item["lookup"]["dateRange"] == {"from": "2014-01-01", "to": "2014-01-03"}

        reopened_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        reopened_item = reopened_response.json()["item"]
        if reopened_item["status"] == "running":
            assert reopened_item["lastAttemptAt"]
            assert reopened_item["lookup"]["registrationNumber"] == "DLU8613F"
            assert reopened_item["lookup"]["dateRange"] == {"from": "2014-01-01", "to": "2014-01-03"}

        final_item = _wait_for_vehicle_report_state(client, request_id, "4")
        assert final_item["report"]["registration_number"] == "DLU8613F"
        assert final_item["report"]["first_registration_date"] == "2014-01-02"


def test_vehicle_report_reopen_after_miss_preserves_last_attempted_date_range(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", lambda url, **kwargs: _fake_identity())
    monkeypatch.setattr(
        service_module.VehicleHistoryClient,
        "fetch_report",
        lambda self, registration_number, vin_number, first_registration_date: (_ for _ in ()).throw(
            RuntimeError("HistoriaPojazdu vehicle-data failed with HTTP 404: Not Found")
        ),
    )

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        initial_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert initial_response.status_code == 200
        assert initial_response.json()["item"]["status"] == "needs_input"

        lookup_response = client.post(
            f"/api/requests/{request_id}/listings/4/vehicle-report/lookup",
            json={
                "registrationNumber": "DLU8613F",
                "dateFrom": "2014-01-10",
                "dateTo": "2014-01-12",
            },
        )
        assert lookup_response.status_code == 200

        final_item = _wait_for_vehicle_report_state(client, request_id, "4")
        assert final_item["status"] == "needs_input"
        assert final_item["lookup"]["dateRange"] == {"from": "2014-01-10", "to": "2014-01-12"}
        assert final_item["lookupOptions"]["dateRange"] == {"from": "2014-01-10", "to": "2014-01-12"}

        reopened_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        reopened_item = reopened_response.json()["item"]
        assert reopened_item["status"] == "needs_input"
        assert reopened_item["lookup"]["dateRange"] == {"from": "2014-01-10", "to": "2014-01-12"}
        assert reopened_item["lookupOptions"]["dateRange"] == {"from": "2014-01-10", "to": "2014-01-12"}


def test_orphaned_running_vehicle_report_lookup_is_recovered_on_service_restart(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

    status_path = service._vehicle_report_status_path(request_id, "4")
    service._write_vehicle_report_status(
        status_path,
        status="running",
        identity=_fake_identity(),
        progress_message="Checking 2014-01-10...",
        lookup={
            "registrationNumber": "DLU8613F",
            "dateRange": {"from": "2014-01-10", "to": "2014-01-12"},
            "currentDate": "2014-01-10",
        },
    )

    restarted_service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    restarted_app = create_app(data_dir=tmp_path, service=restarted_service)

    with TestClient(restarted_app) as client:
        response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert response.status_code == 200
        item = response.json()["item"]
        assert item["status"] == "needs_input"
        assert item["error"] == "The previous vehicle report lookup was interrupted. Please try again."
        assert item["lookup"]["dateRange"] == {"from": "2014-01-10", "to": "2014-01-12"}
        assert item["lookupOptions"]["dateRange"] == {"from": "2014-01-10", "to": "2014-01-12"}
        assert item["identity"]["vin"] == "WDDSJ4EB2EN056917"


def test_orphaned_cancelling_vehicle_report_lookup_is_recovered_on_service_restart(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

    status_path = service._vehicle_report_status_path(request_id, "4")
    service._write_vehicle_report_status(
        status_path,
        status="cancelling",
        identity=_fake_identity(),
        error="Vehicle report lookup cancellation requested.",
        progress_message="Cancelling vehicle report lookup...",
        lookup={
            "registrationNumber": "DLU8613F",
            "dateRange": {"from": "2014-01-10", "to": "2014-01-12"},
            "currentDate": "2014-01-10",
        },
    )

    restarted_service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    restarted_app = create_app(data_dir=tmp_path, service=restarted_service)

    with TestClient(restarted_app) as client:
        response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert response.status_code == 200
        item = response.json()["item"]
        assert item["status"] == "needs_input"
        assert item["error"] == "The previous vehicle report lookup was interrupted. Please try again."
        assert item["lookup"]["dateRange"] == {"from": "2014-01-10", "to": "2014-01-12"}
        assert item["lookupOptions"]["dateRange"] == {"from": "2014-01-10", "to": "2014-01-12"}
        assert item["identity"]["vin"] == "WDDSJ4EB2EN056917"


def test_vehicle_report_lookup_unexpected_worker_failure_transitions_to_failed(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", lambda url, **kwargs: _fake_identity())

    def fake_fetch_report(self, registration_number: str, vin_number: str, first_registration_date: str) -> VehicleHistoryReport:
        if first_registration_date == "2014-01-01":
            raise RuntimeError("HistoriaPojazdu vehicle-data failed with HTTP 404: Not Found")
        raise ValueError("boom")

    monkeypatch.setattr(service_module.VehicleHistoryClient, "fetch_report", fake_fetch_report)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        initial_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert initial_response.status_code == 200
        assert initial_response.json()["item"]["status"] == "needs_input"

        lookup_response = client.post(
            f"/api/requests/{request_id}/listings/4/vehicle-report/lookup",
            json={
                "registrationNumber": "DLU8613F",
                "dateFrom": "2014-01-01",
                "dateTo": "2014-01-02",
            },
        )
        assert lookup_response.status_code == 200

        final_item = _wait_for_vehicle_report_status(client, request_id, "4", "failed")
        assert final_item["status"] == "failed"
        assert "Vehicle report lookup stopped unexpectedly: boom" == final_item["error"]
        assert final_item["lastAttemptAt"]
        assert final_item["lookup"]["dateRange"] == {"from": "2014-01-01", "to": "2014-01-02"}
        assert final_item["lookupOptions"]["dateRange"] == {"from": "2014-01-01", "to": "2014-01-02"}


def test_vehicle_report_regenerate_is_blocked_while_async_lookup_is_running(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", lambda url, **kwargs: _fake_identity())

    def fake_fetch_report(self, registration_number: str, vin_number: str, first_registration_date: str) -> VehicleHistoryReport:
        if first_registration_date == "2014-01-01":
            raise RuntimeError("HistoriaPojazdu vehicle-data failed with HTTP 404: Not Found")
        time.sleep(0.25)
        if first_registration_date == "2014-01-02":
            report = _fake_history_report()
            report.first_registration_date = first_registration_date
            return report
        raise RuntimeError("HistoriaPojazdu vehicle-data failed with HTTP 404: Not Found")

    monkeypatch.setattr(service_module.VehicleHistoryClient, "fetch_report", fake_fetch_report)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        initial_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert initial_response.status_code == 200
        assert initial_response.json()["item"]["status"] == "needs_input"

        lookup_response = client.post(
            f"/api/requests/{request_id}/listings/4/vehicle-report/lookup",
            json={
                "registrationNumber": "DLU8613F",
                "dateFrom": "2014-01-01",
                "dateTo": "2014-01-03",
            },
        )
        assert lookup_response.status_code == 200
        assert lookup_response.json()["item"]["status"] == "running"

        regenerate_response = client.post(f"/api/requests/{request_id}/listings/4/vehicle-report/regenerate")
        assert regenerate_response.status_code == 502
        assert regenerate_response.json()["detail"] == "A vehicle report lookup is already running for this listing."

        final_item = _wait_for_vehicle_report_state(client, request_id, "4")
        assert final_item["report"]["first_registration_date"] == "2014-01-02"


def test_vehicle_report_lookup_can_be_cancelled(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)
    bootstrap_calls: list[int] = []

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", lambda url, **kwargs: _fake_identity())

    def fake_bootstrap_session(self) -> object:
        bootstrap_calls.append(id(self))
        token = object()
        self._bootstrap_context = token
        return token

    def fake_fetch_report(self, registration_number: str, vin_number: str, first_registration_date: str) -> VehicleHistoryReport:
        time.sleep(0.2)
        raise RuntimeError("HistoriaPojazdu vehicle-data failed with HTTP 404: Not Found")

    monkeypatch.setattr(service_module.VehicleHistoryClient, "bootstrap_session", fake_bootstrap_session)
    monkeypatch.setattr(service_module.VehicleHistoryClient, "fetch_report", fake_fetch_report)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        initial_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert initial_response.status_code == 200
        assert initial_response.json()["item"]["status"] == "needs_input"

        lookup_response = client.post(
            f"/api/requests/{request_id}/listings/4/vehicle-report/lookup",
            json={
                "registrationNumber": "DLU 8613F",
                "dateFrom": "2014-01-01",
                "dateTo": "2014-01-03",
            },
        )
        assert lookup_response.status_code == 200
        assert lookup_response.json()["item"]["status"] == "running"

        cancel_response = client.post(f"/api/requests/{request_id}/listings/4/vehicle-report/lookup/cancel")
        assert cancel_response.status_code == 200
        assert cancel_response.json()["item"]["status"] == "cancelling"
        assert cancel_response.json()["item"]["progressMessage"] == "Cancelling vehicle report lookup..."
        assert cancel_response.json()["item"]["lookup"]["registrationNumber"] == "DLU8613F"

        final_item = _wait_for_vehicle_report_status(client, request_id, "4", "cancelled")
        assert final_item["status"] == "cancelled"
        assert final_item["error"] == "Vehicle report lookup was cancelled."
        assert final_item["lookup"]["dateRange"] == {"from": "2014-01-01", "to": "2014-01-03"}
        assert final_item["lookupOptions"]["registrationNumber"] == "DLU8613F"
        assert len(bootstrap_calls) == 1


def test_vehicle_report_regenerate_is_blocked_while_lookup_is_cancelling(monkeypatch, tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    monkeypatch.setattr(service_module, "fetch_otomoto_vehicle_identity", lambda url, **kwargs: _fake_identity())

    def fake_fetch_report(self, registration_number: str, vin_number: str, first_registration_date: str) -> VehicleHistoryReport:
        time.sleep(0.25)
        raise RuntimeError("HistoriaPojazdu vehicle-data failed with HTTP 404: Not Found")

    monkeypatch.setattr(service_module.VehicleHistoryClient, "fetch_report", fake_fetch_report)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

        initial_response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert initial_response.status_code == 200
        assert initial_response.json()["item"]["status"] == "needs_input"

        lookup_response = client.post(
            f"/api/requests/{request_id}/listings/4/vehicle-report/lookup",
            json={
                "registrationNumber": "DLU8613F",
                "dateFrom": "2014-01-01",
                "dateTo": "2014-01-03",
            },
        )
        assert lookup_response.status_code == 200
        assert lookup_response.json()["item"]["status"] == "running"

        cancel_response = client.post(f"/api/requests/{request_id}/listings/4/vehicle-report/lookup/cancel")
        assert cancel_response.status_code == 200
        assert cancel_response.json()["item"]["status"] == "cancelling"

        regenerate_response = client.post(f"/api/requests/{request_id}/listings/4/vehicle-report/regenerate")
        assert regenerate_response.status_code == 502
        assert regenerate_response.json()["detail"] == "A vehicle report lookup is already running for this listing."

        final_item = _wait_for_vehicle_report_status(client, request_id, "4", "cancelled")
        assert final_item["status"] == "cancelled"


def test_vehicle_report_lookup_cancel_rejects_stale_persisted_running_state(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

    status_path = service._vehicle_report_status_path(request_id, "4")
    service._write_vehicle_report_status(
        status_path,
        status="running",
        identity=_fake_identity(),
        progress_message="Checking 2014-01-10...",
        lookup={
            "registrationNumber": "DLU8613F",
            "dateRange": {"from": "2014-01-10", "to": "2014-01-12"},
            "currentDate": "2014-01-10",
        },
    )

    with TestClient(app) as client:
        cancel_response = client.post(f"/api/requests/{request_id}/listings/4/vehicle-report/lookup/cancel")
        assert cancel_response.status_code == 409
        assert cancel_response.json()["detail"] == "No active vehicle report lookup is currently running for this listing."


def test_vehicle_report_lookup_cancel_does_not_overwrite_just_finished_success(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)
    listing = service._resolve_listing_for_report(request_id, "4")
    cache_path = service._vehicle_report_path(request_id, "4")
    status_path = service._vehicle_report_status_path(request_id, "4")
    payload = service._build_vehicle_report_payload(listing, _fake_identity(), _fake_history_report())
    service._write_vehicle_report_status(
        status_path,
        status="success",
        retrieved_at=payload["retrievedAt"],
        identity=_fake_identity(),
    )
    cache_path.write_text(json.dumps(payload), encoding="utf-8")

    future_key = (request_id, "4")
    with service._lock:
        service._report_futures[future_key] = Future()
        service._report_cancel_events[future_key] = threading.Event()

    item = service.cancel_vehicle_report_lookup(request_id, "4")
    recovered_status = json.loads(status_path.read_text(encoding="utf-8"))

    assert item["report"]["first_registration_date"] == "2014-01-01"
    assert recovered_status["status"] == "success"


def test_vehicle_report_lookup_cancel_does_not_overwrite_finished_cancelled_state(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

    listing = service._resolve_listing_for_report(request_id, "4")
    status_path = service._vehicle_report_status_path(request_id, "4")
    future_key = (request_id, "4")

    service._write_vehicle_report_status(
        status_path,
        status="running",
        identity=_fake_identity(),
        progress_message="Checking 2014-01-10...",
        lookup={
            "registrationNumber": "DLU8613F",
            "vin": "WDDSJ4EB2EN056917",
            "dateRange": {"from": "2014-01-10", "to": "2014-01-12"},
            "currentDate": "2014-01-10",
        },
    )

    class _CancelEvent:
        def __init__(self) -> None:
            self._is_set = False

        def set(self) -> None:
            self._is_set = True
            service._write_cancelled_vehicle_report_status(
                status_path,
                identity=_fake_identity(),
                registration_number="DLU8613F",
                date_from="2014-01-10",
                date_to="2014-01-12",
            )

        def is_set(self) -> bool:
            return self._is_set

    with service._lock:
        service._report_futures[future_key] = Future()
        service._report_cancel_events[future_key] = _CancelEvent()

    item = service.cancel_vehicle_report_lookup(request_id, "4")
    final_status = json.loads(status_path.read_text(encoding="utf-8"))

    assert item["status"] == "cancelled"
    assert item["error"] == "Vehicle report lookup was cancelled."
    assert final_status["status"] == "cancelled"


def test_vehicle_report_lookup_cancel_does_not_overwrite_finished_terminal_state(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        _wait_until_ready(client, request_id)

    listing = service._resolve_listing_for_report(request_id, "4")
    status_path = service._vehicle_report_status_path(request_id, "4")
    future_key = (request_id, "4")

    terminal_statuses = [
        (
            "needs_input",
            {
                "status": "needs_input",
                "error": "No report was found in that date range. Try another date range.",
                "lookup": {
                    "registrationNumber": "DLU8613F",
                    "vin": "WDDSJ4EB2EN056917",
                    "dateRange": {"from": "2014-01-10", "to": "2014-01-12"},
                },
                "lookup_options": {
                    "reason": "upstream_404",
                    "vin": "WDDSJ4EB2EN056917",
                    "registrationNumber": "DLU8613F",
                    "firstRegistrationDate": None,
                    "dateRange": {"from": "2014-01-10", "to": "2014-01-12"},
                    "error": "No report was found in that date range. Try another date range.",
                },
            },
        ),
        (
            "failed",
            {
                "status": "failed",
                "error": "Vehicle report lookup stopped unexpectedly: boom",
                "lookup": {
                    "registrationNumber": "DLU8613F",
                    "vin": "WDDSJ4EB2EN056917",
                    "dateRange": {"from": "2014-01-10", "to": "2014-01-12"},
                },
                "lookup_options": {
                    "reason": "upstream_404",
                    "vin": "WDDSJ4EB2EN056917",
                    "registrationNumber": "DLU8613F",
                    "firstRegistrationDate": None,
                    "dateRange": {"from": "2014-01-10", "to": "2014-01-12"},
                    "error": "Vehicle report lookup stopped unexpectedly: boom",
                },
            },
        ),
    ]

    class _TerminalCancelEvent:
        def __init__(self, payload: dict) -> None:
            self._is_set = False
            self.payload = payload

        def set(self) -> None:
            self._is_set = True
            service._write_vehicle_report_status(
                status_path,
                status=self.payload["status"],
                error=self.payload["error"],
                identity=_fake_identity(),
                lookup=self.payload["lookup"],
                lookup_options=self.payload["lookup_options"],
            )

        def is_set(self) -> bool:
            return self._is_set

    for expected_status, payload in terminal_statuses:
        service._write_vehicle_report_status(
            status_path,
            status="running",
            identity=_fake_identity(),
            progress_message="Checking 2014-01-10...",
            lookup={
                "registrationNumber": "DLU8613F",
                "vin": "WDDSJ4EB2EN056917",
                "dateRange": {"from": "2014-01-10", "to": "2014-01-12"},
                "currentDate": "2014-01-10",
            },
        )
        with service._lock:
            service._report_futures[future_key] = Future()
            service._report_cancel_events[future_key] = _TerminalCancelEvent(payload)

        item = service.cancel_vehicle_report_lookup(request_id, "4")
        final_status = json.loads(status_path.read_text(encoding="utf-8"))

        assert item["status"] == expected_status
        assert final_status["status"] == expected_status
        assert final_status["lastError"] == payload["error"]
        assert final_status["lookupOptions"]["error"] == payload["lookup_options"]["error"]


def test_vehicle_report_endpoint_waits_for_ready_results(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path, parser_runner=FakeParserRunner(), parser_options={})
    app = create_app(data_dir=tmp_path, service=service)

    with TestClient(app) as client:
        create_response = client.post(
            "/api/requests",
            json={"url": "https://www.otomoto.pl/osobowe?search%5Border%5D=created_at_first%3Adesc"},
        )
        request_id = create_response.json()["item"]["id"]
        service.store.update_request(request_id, resultsReady=False, status="running")

        response = client.get(f"/api/requests/{request_id}/listings/4/vehicle-report")
        assert response.status_code == 409
