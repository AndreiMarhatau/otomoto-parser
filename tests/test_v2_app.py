from __future__ import annotations

import json
import time
from pathlib import Path
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
    )


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
