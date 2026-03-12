from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from otomoto_parser.v1.parser import RUN_MODE_APPEND_NEWER, RUN_MODE_FULL, RUN_MODE_RESUME
from otomoto_parser.v2 import app as app_module
from otomoto_parser.v2.app import create_app
from otomoto_parser.v2.service import (
    CATEGORY_DATA_NOT_VERIFIED,
    CATEGORY_IMPORTED_FROM_US,
    CATEGORY_PRICE_OUT_OF_RANGE,
    CATEGORY_TO_BE_CHECKED,
    ParserAppService,
    build_categorized_payload,
)


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
