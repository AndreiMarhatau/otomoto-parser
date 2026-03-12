from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from ..v1.aggregation import generate_aggregations
from ..v1.parser import RUN_MODE_APPEND_NEWER, RUN_MODE_FULL, RUN_MODE_RESUME, parse_pages

CATEGORY_PRICE_OUT_OF_RANGE = "Price evaluation out of range"
CATEGORY_DATA_NOT_VERIFIED = "Data not verified"
CATEGORY_IMPORTED_FROM_US = "Imported from US"
CATEGORY_TO_BE_CHECKED = "To be checked"

REQUEST_STATUS_PENDING = "pending"
REQUEST_STATUS_RUNNING = "running"
REQUEST_STATUS_CATEGORIZING = "categorizing"
REQUEST_STATUS_READY = "ready"
REQUEST_STATUS_FAILED = "failed"

ParserRunner = Callable[..., Any]


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _param_map(parameters: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for param in parameters or []:
        if not isinstance(param, dict):
            continue
        key = param.get("key") or param.get("name")
        if isinstance(key, str) and key:
            result[key] = param
    return result


def _param_display(parameters: dict[str, dict[str, Any]], key: str) -> str | None:
    param = parameters.get(key)
    if not param:
        return None
    value = param.get("displayValue") or param.get("value")
    return str(value) if value not in (None, "") else None


def _location_display(location: Any) -> str | None:
    if not isinstance(location, dict):
        return None
    city = location.get("city")
    region = location.get("region")

    def _name(part: Any) -> str | None:
        if isinstance(part, str) and part:
            return part
        if isinstance(part, dict):
            name = part.get("name")
            if isinstance(name, str) and name:
                return name
        return None

    city_name = _name(city)
    region_name = _name(region)
    if city_name and region_name:
        return f"{city_name}, {region_name}"
    return city_name or region_name


def _price_evaluation_display(price_evaluation: Any) -> str | None:
    if not isinstance(price_evaluation, dict):
        return None
    for key in ("indicator", "rating"):
        value = price_evaluation.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _price_fields(node: dict[str, Any]) -> tuple[int | str | None, str]:
    price = node.get("price") if isinstance(node.get("price"), dict) else {}
    amount = price.get("amount") if isinstance(price.get("amount"), dict) else {}
    value = amount.get("units")
    if value in (None, ""):
        value = price.get("value")
    currency = amount.get("currencyCode") or price.get("currency") or "PLN"
    return value, currency


def summarize_record(record: dict[str, Any]) -> dict[str, Any]:
    node = record.get("node") if isinstance(record.get("node"), dict) else {}
    parameters = _param_map(node.get("parameters"))
    country_origin = parameters.get("country_origin", {}).get("value")
    price_amount, price_currency = _price_fields(node)
    price_evaluation = node.get("priceEvaluation")
    price_evaluation_label = _price_evaluation_display(price_evaluation)
    data_verified = node.get("cepikVerified")

    category = CATEGORY_TO_BE_CHECKED
    if not price_evaluation:
        category = CATEGORY_PRICE_OUT_OF_RANGE
    elif data_verified is False:
        category = CATEGORY_DATA_NOT_VERIFIED
    elif isinstance(country_origin, str) and country_origin.lower() == "us":
        category = CATEGORY_IMPORTED_FROM_US

    return {
        "id": record.get("item_id") or record.get("item_key"),
        "category": category,
        "title": node.get("title"),
        "shortDescription": node.get("shortDescription"),
        "url": node.get("url"),
        "imageUrl": ((node.get("thumbnail") or {}).get("x2")) or ((node.get("thumbnail") or {}).get("x1")),
        "price": price_amount,
        "priceCurrency": price_currency,
        "priceEvaluation": price_evaluation_label,
        "dataVerified": bool(data_verified) if isinstance(data_verified, bool) else None,
        "engineCapacity": _param_display(parameters, "engine_capacity"),
        "enginePower": _param_display(parameters, "engine_power"),
        "year": _param_display(parameters, "year"),
        "mileage": _param_display(parameters, "mileage"),
        "fuelType": _param_display(parameters, "fuel_type"),
        "transmission": _param_display(parameters, "gearbox"),
        "location": _location_display(node.get("location")),
        "createdAt": node.get("createdAt"),
        "countryOrigin": parameters.get("country_origin", {}).get("displayValue") or country_origin,
    }


def build_categorized_payload(results_path: Path) -> dict[str, Any]:
    listings: list[dict[str, Any]] = []
    for line in results_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        listings.append(summarize_record(json.loads(line)))

    categories = {
        CATEGORY_PRICE_OUT_OF_RANGE: [],
        CATEGORY_DATA_NOT_VERIFIED: [],
        CATEGORY_IMPORTED_FROM_US: [],
        CATEGORY_TO_BE_CHECKED: [],
    }
    for listing in listings:
        categories[listing["category"]].append(listing)

    return {
        "generatedAt": utc_now(),
        "totalCount": len(listings),
        "categories": {
            name: {
                "label": name,
                "count": len(items),
                "items": items,
            }
            for name, items in categories.items()
        },
    }


@dataclass(frozen=True)
class RequestPaths:
    request_dir: Path
    results_path: Path
    state_path: Path
    categorized_path: Path
    excel_path: Path


class RequestStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            _write_json(self.path, {"requests": []})

    def _load(self) -> list[dict[str, Any]]:
        payload = _read_json(self.path, {"requests": []})
        requests = payload.get("requests", [])
        if not isinstance(requests, list):
            return []
        return requests

    def _save(self, requests: list[dict[str, Any]]) -> None:
        _write_json(self.path, {"requests": requests})

    def list_requests(self) -> list[dict[str, Any]]:
        with self._lock:
            requests = self._load()
        return sorted(requests, key=lambda item: item["createdAt"], reverse=True)

    def get_request(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            for request in self._load():
                if request["id"] == request_id:
                    return request
        return None

    def create_request(self, request: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            requests = self._load()
            requests.append(request)
            self._save(requests)
        return request

    def update_request(self, request_id: str, **changes: Any) -> dict[str, Any]:
        with self._lock:
            requests = self._load()
            for index, request in enumerate(requests):
                if request["id"] != request_id:
                    continue
                updated = {**request, **changes, "updatedAt": utc_now()}
                requests[index] = updated
                self._save(requests)
                return updated
        raise KeyError(request_id)


class ParserAppService:
    def __init__(
        self,
        data_dir: Path,
        *,
        parser_runner: ParserRunner = parse_pages,
        parser_options: dict[str, Any] | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.store = RequestStore(self.data_dir / "requests.json")
        self.parser_runner = parser_runner
        self.parser_options = parser_options or {}
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="parser-app")
        self._futures: dict[str, Future[Any]] = {}
        self._lock = threading.Lock()
        self._recover_in_progress_requests()

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)

    def _recover_in_progress_requests(self) -> None:
        for request in self.store.list_requests():
            if request["status"] in {REQUEST_STATUS_PENDING, REQUEST_STATUS_RUNNING, REQUEST_STATUS_CATEGORIZING}:
                self.store.update_request(
                    request["id"],
                    status=REQUEST_STATUS_FAILED,
                    error="The application stopped while this request was still running.",
                    progressMessage="Interrupted during the previous run.",
                )

    def request_paths(self, request_id: str) -> RequestPaths:
        request_dir = self.data_dir / "requests" / request_id
        return RequestPaths(
            request_dir=request_dir,
            results_path=request_dir / "results.jsonl",
            state_path=request_dir / "state.json",
            categorized_path=request_dir / "categorized.json",
            excel_path=request_dir / "aggregations.xlsx",
        )

    def list_requests(self) -> list[dict[str, Any]]:
        return self.store.list_requests()

    def get_request(self, request_id: str) -> dict[str, Any]:
        request = self.store.get_request(request_id)
        if request is None:
            raise KeyError(request_id)
        return request

    def create_request(self, source_url: str) -> dict[str, Any]:
        now = utc_now()
        request_id = uuid.uuid4().hex[:12]
        paths = self.request_paths(request_id)
        request = {
            "id": request_id,
            "sourceUrl": source_url,
            "createdAt": now,
            "updatedAt": now,
            "status": REQUEST_STATUS_PENDING,
            "progressMessage": "Queued for initial import.",
            "pagesCompleted": 0,
            "resultsWritten": 0,
            "hasMore": True,
            "error": None,
            "lastRunMode": RUN_MODE_FULL,
            "resultsReady": False,
            "excelReady": False,
            "runDir": str(paths.request_dir),
            "resultsPath": str(paths.results_path),
            "statePath": str(paths.state_path),
            "categorizedPath": str(paths.categorized_path),
            "excelPath": str(paths.excel_path),
        }
        self.store.create_request(request)
        self.start_run(request_id, RUN_MODE_FULL)
        return self.get_request(request_id)

    def start_run(self, request_id: str, mode: str) -> dict[str, Any]:
        request = self.get_request(request_id)
        with self._lock:
            future = self._futures.get(request_id)
            if future is not None and not future.done():
                return request

        updated = self.store.update_request(
            request_id,
            status=REQUEST_STATUS_PENDING,
            progressMessage="Queued.",
            error=None,
            lastRunMode=mode,
            resultsReady=False if mode == RUN_MODE_FULL else request["resultsReady"],
            excelReady=False if mode == RUN_MODE_FULL else request["excelReady"],
        )
        with self._lock:
            self._futures[request_id] = self.executor.submit(self._run_request, request_id, mode)
        return updated

    def get_results(self, request_id: str) -> dict[str, Any]:
        request = self.get_request(request_id)
        if not request["resultsReady"]:
            raise RuntimeError("Results are not ready yet.")
        return _read_json(Path(request["categorizedPath"]), {})

    def choose_resume_mode(self, request_id: str) -> str:
        request = self.get_request(request_id)
        if request["status"] == REQUEST_STATUS_READY:
            return RUN_MODE_APPEND_NEWER
        if request["lastRunMode"] != RUN_MODE_APPEND_NEWER or not request["resultsReady"]:
            return RUN_MODE_RESUME

        state = _read_json(Path(request["statePath"]), {})
        next_page = state.get("next_page")
        has_more = state.get("has_more")
        if isinstance(next_page, int) and next_page > 1 and has_more is True:
            return RUN_MODE_RESUME
        return RUN_MODE_APPEND_NEWER

    def _update_progress(self, request_id: str, payload: dict[str, Any]) -> None:
        event = payload.get("event")
        if event == "page_fetch_started":
            self.store.update_request(
                request_id,
                status=REQUEST_STATUS_RUNNING,
                progressMessage=f"Fetching page {payload['page']}...",
                pagesCompleted=payload["pages_completed"],
                resultsWritten=payload["results_written"],
            )
            return
        if event == "page_fetch_finished":
            state = payload["state"]
            self.store.update_request(
                request_id,
                status=REQUEST_STATUS_RUNNING,
                progressMessage=f"Fetched page {payload['page']} ({payload['written']} new listings).",
                pagesCompleted=state["pages_completed"],
                resultsWritten=state["results_written"],
            )
            return
        if event == "complete":
            state = payload["state"]
            self.store.update_request(
                request_id,
                status=REQUEST_STATUS_CATEGORIZING,
                progressMessage="Categorizing listings and generating Excel output.",
                pagesCompleted=state["pages_completed"],
                resultsWritten=state["results_written"],
                hasMore=state["has_more"],
            )

    def _run_request(self, request_id: str, mode: str) -> None:
        request = self.get_request(request_id)
        paths = self.request_paths(request_id)
        paths.request_dir.mkdir(parents=True, exist_ok=True)
        if mode == RUN_MODE_FULL:
            for path in (paths.categorized_path, paths.excel_path):
                if path.exists():
                    path.unlink()
        try:
            self.store.update_request(
                request_id,
                status=REQUEST_STATUS_RUNNING,
                progressMessage="Starting parser.",
                error=None,
            )
            self.parser_runner(
                request["sourceUrl"],
                paths.results_path,
                paths.state_path,
                run_mode=mode,
                progress_callback=lambda payload: self._update_progress(request_id, payload),
                **self.parser_options,
            )

            if not paths.results_path.exists():
                raise RuntimeError("Parser finished without any results.")

            generate_aggregations(paths.results_path, paths.excel_path)
            categorized = build_categorized_payload(paths.results_path)
            _write_json(paths.categorized_path, categorized)
            self.store.update_request(
                request_id,
                status=REQUEST_STATUS_READY,
                progressMessage=f"Ready. {categorized['totalCount']} listings categorized.",
                resultsReady=True,
                excelReady=paths.excel_path.exists(),
            )
        except Exception as exc:  # noqa: BLE001
            self.store.update_request(
                request_id,
                status=REQUEST_STATUS_FAILED,
                progressMessage="Request failed.",
                error=str(exc),
            )
        finally:
            with self._lock:
                self._futures.pop(request_id, None)
