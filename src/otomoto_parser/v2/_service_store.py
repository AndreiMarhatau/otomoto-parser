from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from ._service_common import RequestPaths, SettingsState, utc_now
from ._service_json import _mask_secret, _read_json, _write_json


class RequestStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            _write_json(self.path, {"requests": []})

    def _load(self) -> list[dict[str, Any]]:
        payload = _read_json(self.path, {"requests": []})
        return payload.get("requests", []) if isinstance(payload.get("requests"), list) else []

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
                if request["id"] == request_id:
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


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def read(self) -> SettingsState:
        with self._lock:
            payload = _read_json(self.path, {})
        api_key = payload.get("openaiApiKey")
        return SettingsState(openai_api_key=api_key.strip() or None if isinstance(api_key, str) else None)

    def write(self, state: SettingsState) -> SettingsState:
        with self._lock:
            _write_json(self.path, {"openaiApiKey": state.openai_api_key})
        return state


def settings_payload(settings_store) -> dict[str, Any]:
    stored = settings_store.read()
    env_key = __import__("os").environ.get("OPENAI_API_KEY", "").strip() or None
    configured_key = stored.openai_api_key or env_key
    source = "stored" if stored.openai_api_key else "environment" if env_key else None
    return {
        "openaiApiKeyConfigured": configured_key is not None,
        "openaiApiKeySource": source,
        "openaiApiKeyMasked": _mask_secret(configured_key),
        "openaiApiKeyStored": stored.openai_api_key is not None,
    }


def request_paths(data_dir: Path, request_id: str) -> RequestPaths:
    request_dir = data_dir / "requests" / request_id
    return RequestPaths(
        request_dir=request_dir,
        results_path=request_dir / "results.jsonl",
        state_path=request_dir / "state.json",
        categorized_path=request_dir / "categorized.json",
        saved_categories_path=request_dir / "saved-categories.json",
        excel_path=request_dir / "aggregations.xlsx",
        reports_dir=request_dir / "vehicle-reports",
        analyses_dir=request_dir / "red-flag-analyses",
    )
