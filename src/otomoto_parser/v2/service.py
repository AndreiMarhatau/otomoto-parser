from __future__ import annotations

import json
import shutil
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable

from ..v1.history_report import VehicleHistoryClient, VehicleHistoryReport
from ..v1.otomoto_vehicle_identity import OtomotoVehicleIdentity, fetch_otomoto_vehicle_identity
from ..v1.aggregation import generate_aggregations
from ..v1.parser import RUN_MODE_APPEND_NEWER, RUN_MODE_FULL, RUN_MODE_RESUME, parse_pages

CATEGORY_PRICE_OUT_OF_RANGE = "Price evaluation out of range"
CATEGORY_DATA_NOT_VERIFIED = "Data not verified"
CATEGORY_IMPORTED_FROM_US = "Imported from US"
CATEGORY_TO_BE_CHECKED = "To be checked"
CATEGORY_FAVORITES = "Favorites"

SYSTEM_CATEGORY_ORDER = [
    CATEGORY_PRICE_OUT_OF_RANGE,
    CATEGORY_DATA_NOT_VERIFIED,
    CATEGORY_IMPORTED_FROM_US,
    CATEGORY_TO_BE_CHECKED,
]
ASSIGNABLE_CATEGORY_ORDER = [CATEGORY_FAVORITES]

REQUEST_STATUS_PENDING = "pending"
REQUEST_STATUS_RUNNING = "running"
REQUEST_STATUS_CATEGORIZING = "categorizing"
REQUEST_STATUS_READY = "ready"
REQUEST_STATUS_FAILED = "failed"

CUSTOM_CATEGORY_PREFIX = "custom:"

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
        if isinstance(value, str) and value and value.upper() != "NONE":
            return value
    return None


def _is_out_of_range_price_evaluation(price_evaluation: Any) -> bool:
    if not isinstance(price_evaluation, dict) or not price_evaluation:
        return True
    seen_value = False
    for key in ("indicator", "rating"):
        value = price_evaluation.get(key)
        if not isinstance(value, str) or not value:
            continue
        seen_value = True
        if value.upper() != "NONE":
            return False
    return seen_value


def _price_fields(node: dict[str, Any]) -> tuple[int | str | None, str]:
    price = node.get("price") if isinstance(node.get("price"), dict) else {}
    amount = price.get("amount") if isinstance(price.get("amount"), dict) else {}
    value = amount.get("units")
    if value in (None, ""):
        value = price.get("value")
    currency = amount.get("currencyCode") or price.get("currency") or "PLN"
    return value, currency


def _is_us_origin(country_origin: Any) -> bool:
    if not isinstance(country_origin, str):
        return False
    normalized = country_origin.strip().lower()
    return normalized in {"us", "usa", "united-states", "united_states"}


def summarize_record(record: dict[str, Any]) -> dict[str, Any]:
    node = record.get("node") if isinstance(record.get("node"), dict) else {}
    parameters = _param_map(node.get("parameters"))
    country_origin = parameters.get("country_origin", {}).get("value")
    price_amount, price_currency = _price_fields(node)
    price_evaluation = node.get("priceEvaluation")
    price_evaluation_label = _price_evaluation_display(price_evaluation)
    data_verified = node.get("cepikVerified")

    category = CATEGORY_TO_BE_CHECKED
    if _is_out_of_range_price_evaluation(price_evaluation):
        category = CATEGORY_PRICE_OUT_OF_RANGE
    elif data_verified is False:
        category = CATEGORY_DATA_NOT_VERIFIED
    elif _is_us_origin(country_origin):
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
    saved_categories_path: Path
    excel_path: Path
    reports_dir: Path


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

    def delete_request(self, request_id: str) -> None:
        with self._lock:
            requests = self._load()
            filtered = [request for request in requests if request["id"] != request_id]
            if len(filtered) == len(requests):
                raise KeyError(request_id)
            self._save(filtered)


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
        self._request_locks: dict[str, threading.Lock] = {}
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
            saved_categories_path=request_dir / "saved-categories.json",
            excel_path=request_dir / "aggregations.xlsx",
            reports_dir=request_dir / "vehicle-reports",
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
            "savedCategoriesPath": str(paths.saved_categories_path),
            "excelPath": str(paths.excel_path),
        }
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
            updated = self.store.update_request(
                request_id,
                status=REQUEST_STATUS_PENDING,
                progressMessage="Queued.",
                error=None,
                lastRunMode=mode,
                resultsReady=False if mode == RUN_MODE_FULL else request["resultsReady"],
                excelReady=False if mode == RUN_MODE_FULL else request["excelReady"],
            )
            self._futures[request_id] = self.executor.submit(self._run_request, request_id, mode)
        return updated

    def get_results(
        self,
        request_id: str,
        *,
        category: str | None = None,
        page: int = 1,
        page_size: int = 12,
    ) -> dict[str, Any]:
        request = self.get_request(request_id)
        if not request["resultsReady"]:
            raise RuntimeError("Results are not ready yet.")
        payload = _read_json(Path(request["categorizedPath"]), {})
        raw_categories = payload.get("categories", {})
        if not isinstance(raw_categories, dict):
            raw_categories = {}
        saved_categories = self._read_saved_categories(request_id)
        listing_index = self._build_listing_index(raw_categories)
        categories = self._build_result_categories(raw_categories, saved_categories, listing_index)

        current_category = category if category in categories else next(iter(categories.keys()), None)
        if current_category is None:
            return {
                "requestId": request_id,
                "generatedAt": payload.get("generatedAt") or utc_now(),
                "totalCount": payload.get("totalCount", 0),
                "categories": {},
                "assignableCategories": self._serialize_assignable_categories(saved_categories),
                "items": [],
                "pagination": {"page": 1, "pageSize": page_size, "totalPages": 1, "totalItems": 0},
                "currentCategory": None,
            }

        selected = categories.get(current_category, {})
        all_items = selected.get("items", []) if isinstance(selected, dict) else []
        if not isinstance(all_items, list):
            all_items = []
        safe_page_size = max(1, page_size)
        total_items = len(all_items)
        total_pages = max(1, (total_items + safe_page_size - 1) // safe_page_size)
        safe_page = min(max(1, page), total_pages)
        start_index = (safe_page - 1) * safe_page_size
        current_items = [dict(item) for item in all_items[start_index : start_index + safe_page_size] if isinstance(item, dict)]
        self._attach_report_cache_metadata(request_id, current_items)
        self._attach_saved_category_metadata(request_id, current_items)
        return {
            "requestId": request_id,
            "generatedAt": payload.get("generatedAt") or utc_now(),
            "totalCount": payload.get("totalCount", 0),
            "categories": {
                name: {
                    "label": value.get("label", name),
                    "count": value.get("count", 0),
                    "kind": value.get("kind", "system"),
                    "editable": bool(value.get("editable")),
                    "deletable": bool(value.get("deletable")),
                }
                for name, value in categories.items()
                if isinstance(value, dict)
            },
            "assignableCategories": self._serialize_assignable_categories(saved_categories),
            "currentCategory": current_category,
            "items": current_items,
            "pagination": {
                "page": safe_page,
                "pageSize": safe_page_size,
                "totalPages": total_pages,
                "totalItems": total_items,
            },
        }

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

    def delete_request(self, request_id: str) -> None:
        request_lock = self._request_lock(request_id)
        with self._lock:
            future = self._futures.get(request_id)
            if future is not None and not future.done():
                raise RuntimeError("Cannot delete a request while it is still running.")
        with request_lock:
            with self._lock:
                future = self._futures.get(request_id)
                if future is not None and not future.done():
                    raise RuntimeError("Cannot delete a request while it is still running.")
            request = self.get_request(request_id)
            shutil.rmtree(Path(request["runDir"]), ignore_errors=True)
            self.store.delete_request(request_id)
        with self._lock:
            self._request_locks.pop(request_id, None)

    def create_saved_category(self, request_id: str, name: str) -> dict[str, Any]:
        with self._request_lock(request_id):
            self.get_request(request_id)
            cleaned = self._normalize_category_name(name)
            state = self._read_saved_categories(request_id)
            self._ensure_unique_saved_category_name(state, cleaned)
            key = f"{CUSTOM_CATEGORY_PREFIX}{uuid.uuid4().hex[:10]}"
            state["categories"].append({"key": key, "label": cleaned})
            self._write_saved_categories(request_id, state)
            return {"key": key, "label": cleaned, "editable": True, "deletable": True, "kind": "saved"}

    def rename_saved_category(self, request_id: str, category_key: str, name: str) -> dict[str, Any]:
        with self._request_lock(request_id):
            self.get_request(request_id)
            if not category_key.startswith(CUSTOM_CATEGORY_PREFIX):
                raise RuntimeError("This category cannot be renamed.")
            cleaned = self._normalize_category_name(name)
            state = self._read_saved_categories(request_id)
            self._ensure_unique_saved_category_name(state, cleaned, ignore_key=category_key)
            category = self._find_saved_category(state, category_key)
            if category is None:
                raise KeyError(category_key)
            category["label"] = cleaned
            self._write_saved_categories(request_id, state)
            return {"key": category_key, "label": cleaned, "editable": True, "deletable": True, "kind": "saved"}

    def delete_saved_category(self, request_id: str, category_key: str) -> None:
        with self._request_lock(request_id):
            self.get_request(request_id)
            if not category_key.startswith(CUSTOM_CATEGORY_PREFIX):
                raise RuntimeError("This category cannot be removed.")
            state = self._read_saved_categories(request_id)
            categories = [category for category in state["categories"] if category.get("key") != category_key]
            if len(categories) == len(state["categories"]):
                raise KeyError(category_key)
            state["categories"] = categories
            state["assignments"] = {
                listing_id: [key for key in category_keys if key != category_key]
                for listing_id, category_keys in state["assignments"].items()
            }
            self._write_saved_categories(request_id, state)

    def update_listing_saved_categories(self, request_id: str, listing_id: str, category_keys: list[str]) -> dict[str, Any]:
        with self._request_lock(request_id):
            self.get_request(request_id)
            canonical_listing_id = self._resolve_listing_for_report(request_id, listing_id)["id"]
            state = self._read_saved_categories(request_id)
            assignable_keys = {category["key"] for category in self._assignable_categories(state)}
            cleaned = []
            seen: set[str] = set()
            for key in category_keys:
                if not isinstance(key, str) or key not in assignable_keys or key in seen:
                    continue
                cleaned.append(key)
                seen.add(key)
            if len(cleaned) != len([key for key in category_keys if isinstance(key, str)]):
                invalid = [key for key in category_keys if not isinstance(key, str) or key not in assignable_keys]
                if invalid:
                    raise KeyError(str(invalid[0]))
            if cleaned:
                state["assignments"][canonical_listing_id] = cleaned
            else:
                state["assignments"].pop(canonical_listing_id, None)
            self._write_saved_categories(request_id, state)
            return {
                "listingId": canonical_listing_id,
                "savedCategoryKeys": cleaned,
            }

    def get_vehicle_report(self, request_id: str, listing_id: str, *, force_refresh: bool = False) -> dict[str, Any]:
        with self._request_lock(request_id):
            listing = self._resolve_listing_for_report(request_id, listing_id)
            canonical_listing_id = listing["id"]
            cache_path = self._vehicle_report_path(request_id, canonical_listing_id)
            status_path = self._vehicle_report_status_path(request_id, canonical_listing_id)
            if not force_refresh:
                cached = _read_json(cache_path, None)
                if cached is not None:
                    return cached
            url = listing.get("url")
            if not isinstance(url, str) or not url:
                error_message = "Listing URL is missing, so the vehicle report cannot be fetched."
                self._write_vehicle_report_status(status_path, status="failed", error=error_message)
                raise RuntimeError(error_message)
            try:
                identity = fetch_otomoto_vehicle_identity(
                    url,
                    timeout_s=float(self.parser_options.get("request_timeout_s", 45.0)),
                )
                history_client = VehicleHistoryClient(
                    timeout_s=float(self.parser_options.get("request_timeout_s", 45.0)),
                    retry_attempts=int(self.parser_options.get("retry_attempts", 4)),
                    backoff_base_s=float(self.parser_options.get("backoff_base", 1.0)),
                )
                history = history_client.fetch_report(
                    identity.registration_number,
                    identity.vin,
                    identity.first_registration_date,
                )
            except Exception as exc:  # noqa: BLE001
                error_message = f"Could not fetch vehicle report data: {exc}"
                self._write_vehicle_report_status(status_path, status="failed", error=error_message)
                raise RuntimeError(error_message) from exc
            payload = self._build_vehicle_report_payload(listing, identity, history)
            self.get_request(request_id)
            _write_json(cache_path, payload)
            self._write_vehicle_report_status(
                status_path,
                status="success",
                retrieved_at=payload["retrievedAt"],
            )
            return payload

    def _attach_report_cache_metadata(self, request_id: str, items: list[dict[str, Any]]) -> None:
        for item in items:
            if not isinstance(item, dict) or item.get("id") is None:
                continue
            status = _read_json(self._vehicle_report_status_path(request_id, str(item["id"])), {})
            report = _read_json(self._vehicle_report_path(request_id, str(item["id"])), None)
            item["vehicleReport"] = {
                "cached": report is not None,
                "retrievedAt": report.get("retrievedAt") if report else None,
                "status": status.get("status"),
                "lastAttemptAt": status.get("lastAttemptAt"),
                "lastError": status.get("lastError"),
            }

    def _attach_saved_category_metadata(self, request_id: str, items: list[dict[str, Any]]) -> None:
        assignments = self._read_saved_categories(request_id).get("assignments", {})
        if not isinstance(assignments, dict):
            assignments = {}
        for item in items:
            if not isinstance(item, dict) or item.get("id") is None:
                continue
            category_keys = assignments.get(str(item["id"]), [])
            if not isinstance(category_keys, list):
                category_keys = []
            item["savedCategoryKeys"] = [key for key in category_keys if isinstance(key, str)]

    def _find_listing_record(self, request_id: str, listing_id: str) -> dict[str, Any]:
        request = self.get_request(request_id)
        results_path = Path(request["resultsPath"])
        if not results_path.exists():
            raise RuntimeError("The stored results for this request are not available.")
        needle = str(listing_id)
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            candidates = {
                str(record.get("item_id") or ""),
                str(record.get("item_key") or ""),
                str(((record.get("node") or {}).get("id")) or ""),
            }
            if needle in candidates:
                return record
        raise KeyError(listing_id)

    def _build_vehicle_report_payload(
        self,
        listing: dict[str, Any],
        identity: OtomotoVehicleIdentity,
        history: VehicleHistoryReport,
    ) -> dict[str, Any]:
        return {
            "listingId": listing["id"],
            "listingUrl": listing.get("url"),
            "listingTitle": listing.get("title"),
            "retrievedAt": utc_now(),
            "identity": {
                "advertId": identity.advert_id,
                "vin": identity.vin,
                "registrationNumber": identity.registration_number,
                "firstRegistrationDate": identity.first_registration_date,
            },
            "report": asdict(history),
            "summary": self._build_report_summary(history),
        }

    def _vehicle_report_path(self, request_id: str, listing_id: str) -> Path:
        paths = self.request_paths(request_id)
        cache_key = sha256(listing_id.encode("utf-8")).hexdigest()
        return paths.reports_dir / f"{cache_key}.json"

    def _vehicle_report_status_path(self, request_id: str, listing_id: str) -> Path:
        paths = self.request_paths(request_id)
        cache_key = sha256(f"{listing_id}:status".encode("utf-8")).hexdigest()
        return paths.reports_dir / f"{cache_key}.json"

    def _write_vehicle_report_status(
        self,
        path: Path,
        *,
        status: str,
        error: str | None = None,
        retrieved_at: str | None = None,
    ) -> None:
        payload = {
            "status": status,
            "lastAttemptAt": utc_now(),
            "lastError": error,
            "retrievedAt": retrieved_at,
        }
        _write_json(path, payload)

    def _canonical_listing_id(self, record: dict[str, Any]) -> str:
        node = record.get("node") if isinstance(record.get("node"), dict) else {}
        return str(record.get("item_id") or node.get("id") or record.get("item_key") or "")

    def _resolve_listing_for_report(self, request_id: str, listing_id: str) -> dict[str, Any]:
        request = self.get_request(request_id)
        if request["resultsReady"]:
            categorized = _read_json(Path(request["categorizedPath"]), {})
            categories = categorized.get("categories", {})
            if isinstance(categories, dict):
                for category in categories.values():
                    if not isinstance(category, dict):
                        continue
                    for item in category.get("items", []):
                        if isinstance(item, dict) and str(item.get("id")) == str(listing_id):
                            return item

        record = self._find_listing_record(request_id, listing_id)
        node = record.get("node") if isinstance(record.get("node"), dict) else {}
        return {
            "id": self._canonical_listing_id(record),
            "title": node.get("title"),
            "url": node.get("url"),
            "location": _location_display(node.get("location")),
        }

    def _request_lock(self, request_id: str) -> threading.Lock:
        with self._lock:
            lock = self._request_locks.get(request_id)
            if lock is None:
                lock = threading.Lock()
                self._request_locks[request_id] = lock
            return lock

    def _default_saved_categories(self) -> dict[str, Any]:
        return {
            "categories": [],
            "assignments": {},
        }

    def _read_saved_categories(self, request_id: str) -> dict[str, Any]:
        paths = self.request_paths(request_id)
        state = _read_json(paths.saved_categories_path, self._default_saved_categories())
        categories = state.get("categories", [])
        assignments = state.get("assignments", {})
        if not isinstance(categories, list):
            categories = []
        if not isinstance(assignments, dict):
            assignments = {}
        normalized_categories = []
        for category in categories:
            if not isinstance(category, dict):
                continue
            key = category.get("key")
            label = category.get("label")
            if isinstance(key, str) and isinstance(label, str) and key.startswith(CUSTOM_CATEGORY_PREFIX) and label.strip():
                normalized_categories.append({"key": key, "label": label.strip()})
        normalized_assignments = {
            str(listing_id): [key for key in category_keys if isinstance(key, str)]
            for listing_id, category_keys in assignments.items()
            if isinstance(category_keys, list)
        }
        return {
            "categories": normalized_categories,
            "assignments": normalized_assignments,
        }

    def _write_saved_categories(self, request_id: str, state: dict[str, Any]) -> None:
        self.get_request(request_id)
        paths = self.request_paths(request_id)
        _write_json(paths.saved_categories_path, state)

    def _normalize_category_name(self, name: str) -> str:
        cleaned = " ".join(name.split())
        if not cleaned:
            raise RuntimeError("Category name cannot be empty.")
        return cleaned

    def _ensure_unique_saved_category_name(self, state: dict[str, Any], name: str, ignore_key: str | None = None) -> None:
        lowered = name.casefold()
        for category in self._assignable_categories(state):
            key = category["key"]
            if ignore_key is not None and key == ignore_key:
                continue
            if category["label"].casefold() == lowered:
                raise RuntimeError("A category with this name already exists.")

    def _find_saved_category(self, state: dict[str, Any], category_key: str) -> dict[str, Any] | None:
        for category in state.get("categories", []):
            if isinstance(category, dict) and category.get("key") == category_key:
                return category
        return None

    def _assignable_categories(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        categories = [{"key": CATEGORY_FAVORITES, "label": CATEGORY_FAVORITES}]
        for category in state.get("categories", []):
            if isinstance(category, dict):
                categories.append(category)
        return categories

    def _serialize_assignable_categories(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "key": category["key"],
                "label": category["label"],
                "kind": "saved",
                "editable": category["key"].startswith(CUSTOM_CATEGORY_PREFIX),
                "deletable": category["key"].startswith(CUSTOM_CATEGORY_PREFIX),
            }
            for category in self._assignable_categories(state)
        ]

    def _build_listing_index(self, raw_categories: dict[str, Any]) -> dict[str, dict[str, Any]]:
        listing_index: dict[str, dict[str, Any]] = {}
        for category_name in SYSTEM_CATEGORY_ORDER:
            category = raw_categories.get(category_name, {})
            if not isinstance(category, dict):
                continue
            for item in category.get("items", []):
                if not isinstance(item, dict):
                    continue
                listing_id = item.get("id")
                if listing_id is None:
                    continue
                listing_index[str(listing_id)] = dict(item)
        return listing_index

    def _build_result_categories(
        self,
        raw_categories: dict[str, Any],
        saved_categories: dict[str, Any],
        listing_index: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        categories: dict[str, dict[str, Any]] = {}
        for category_name in SYSTEM_CATEGORY_ORDER:
            category = raw_categories.get(category_name, {})
            items = category.get("items", []) if isinstance(category, dict) else []
            categories[category_name] = {
                "label": category_name,
                "count": len(items) if isinstance(items, list) else 0,
                "items": items if isinstance(items, list) else [],
                "kind": "system",
                "editable": False,
                "deletable": False,
            }

        assignments = saved_categories.get("assignments", {})
        if not isinstance(assignments, dict):
            assignments = {}
        for category in self._assignable_categories(saved_categories):
            category_key = category["key"]
            items = []
            for listing_id, category_keys in assignments.items():
                if category_key not in category_keys:
                    continue
                item = listing_index.get(str(listing_id))
                if item is not None:
                    items.append(dict(item))
            categories[category_key] = {
                "label": category["label"],
                "count": len(items),
                "items": items,
                "kind": "saved",
                "editable": category_key.startswith(CUSTOM_CATEGORY_PREFIX),
                "deletable": category_key.startswith(CUSTOM_CATEGORY_PREFIX),
            }
        return categories

    def _build_report_summary(self, history: VehicleHistoryReport) -> dict[str, Any]:
        technical_data = history.technical_data.get("technicalData", {})
        basic_data = technical_data.get("basicData", {}) if isinstance(technical_data, dict) else {}
        ownership_history = technical_data.get("ownershipHistory", {}) if isinstance(technical_data, dict) else {}
        autodna_unavailable = isinstance(history.autodna_data, dict) and history.autodna_data.get("unavailable") is True
        carfax_unavailable = isinstance(history.carfax_data, dict) and history.carfax_data.get("unavailable") is True
        return {
            "make": basic_data.get("make"),
            "model": basic_data.get("model"),
            "variant": basic_data.get("type"),
            "modelYear": basic_data.get("modelYear"),
            "fuelType": basic_data.get("fuel"),
            "engineCapacity": basic_data.get("engineCapacity"),
            "enginePower": basic_data.get("enginePower"),
            "bodyType": basic_data.get("bodyType"),
            "color": basic_data.get("color"),
            "ownersCount": ownership_history.get("numberOfOwners"),
            "coOwnersCount": ownership_history.get("numberOfCoowners"),
            "lastOwnershipChange": ownership_history.get("dateOfLastOwnershipChange"),
            "autodnaAvailable": bool(history.autodna_data) and not autodna_unavailable,
            "carfaxAvailable": bool(history.carfax_data) and not carfax_unavailable,
            "autodnaUnavailable": autodna_unavailable,
            "carfaxUnavailable": carfax_unavailable,
        }

    def _prune_saved_category_assignments(self, request_id: str, valid_listing_ids: set[str]) -> None:
        state = self._read_saved_categories(request_id)
        state["assignments"] = {
            listing_id: category_keys
            for listing_id, category_keys in state.get("assignments", {}).items()
            if listing_id in valid_listing_ids
        }
        self._write_saved_categories(request_id, state)

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
            if mode == RUN_MODE_FULL:
                valid_listing_ids = {
                    str(item.get("id"))
                    for category in categorized.get("categories", {}).values()
                    if isinstance(category, dict)
                    for item in category.get("items", [])
                    if isinstance(item, dict) and item.get("id") is not None
                }
                with self._request_lock(request_id):
                    self._prune_saved_category_assignments(request_id, valid_listing_ids)
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
