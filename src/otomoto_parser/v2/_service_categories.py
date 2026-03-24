from __future__ import annotations

from pathlib import Path
from typing import Any

from ._service_common import CATEGORY_FAVORITES, CUSTOM_CATEGORY_PREFIX, SYSTEM_CATEGORY_ORDER, utc_now
from ._service_json import _read_json, _write_json


class ServiceCategoryMixin:
    def get_results(self, request_id: str, *, category: str | None = None, page: int = 1, page_size: int = 12) -> dict[str, Any]:
        request = self.get_request(request_id)
        if not request["resultsReady"]:
            raise RuntimeError("Results are not ready yet.")
        payload = _read_json(Path(request["categorizedPath"]), {})
        raw_categories = payload.get("categories", {}) if isinstance(payload.get("categories"), dict) else {}
        saved_categories = self._read_saved_categories(request_id)
        categories = self._build_result_categories(raw_categories, saved_categories, self._build_listing_index(raw_categories))
        current_category = category if category in categories else next(iter(categories.keys()), None)
        if current_category is None:
            return self._empty_results_payload(request_id, payload, page_size, saved_categories)
        return self._results_payload(
            request_id,
            {
                "payload": payload,
                "categories": categories,
                "current_category": current_category,
                "page": page,
                "page_size": page_size,
                "saved_categories": saved_categories,
            },
        )

    def create_saved_category(self, request_id: str, name: str) -> dict[str, Any]:
        with self._request_lock(request_id):
            self.get_request(request_id)
            cleaned = self._normalize_category_name(name)
            state = self._read_saved_categories(request_id)
            self._ensure_unique_saved_category_name(state, cleaned)
            key = f"{CUSTOM_CATEGORY_PREFIX}{__import__('uuid').uuid4().hex[:10]}"
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
            state["assignments"] = {listing_id: [key for key in category_keys if key != category_key] for listing_id, category_keys in state["assignments"].items()}
            self._write_saved_categories(request_id, state)

    def update_listing_saved_categories(self, request_id: str, listing_id: str, category_keys: list[str]) -> dict[str, Any]:
        with self._request_lock(request_id):
            canonical_listing_id = self._resolve_listing_for_report(request_id, listing_id)["id"]
            state = self._read_saved_categories(request_id)
            cleaned = self._validated_category_keys(state, category_keys)
            if cleaned:
                state["assignments"][canonical_listing_id] = cleaned
            else:
                state["assignments"].pop(canonical_listing_id, None)
            self._write_saved_categories(request_id, state)
            return {"listingId": canonical_listing_id, "savedCategoryKeys": cleaned}

    def _default_saved_categories(self) -> dict[str, Any]:
        return {"categories": [], "assignments": {}}

    def _read_saved_categories(self, request_id: str) -> dict[str, Any]:
        state = _read_json(self.request_paths(request_id).saved_categories_path, self._default_saved_categories())
        categories = [category for category in state.get("categories", []) if self._valid_saved_category(category)]
        assignments = {str(listing_id): [key for key in category_keys if isinstance(key, str)] for listing_id, category_keys in state.get("assignments", {}).items() if isinstance(category_keys, list)}
        return {"categories": categories, "assignments": assignments}

    def _write_saved_categories(self, request_id: str, state: dict[str, Any]) -> None:
        self.get_request(request_id)
        _write_json(self.request_paths(request_id).saved_categories_path, state)

    def _normalize_category_name(self, name: str) -> str:
        cleaned = " ".join(name.split())
        if not cleaned:
            raise RuntimeError("Category name cannot be empty.")
        return cleaned

    def _ensure_unique_saved_category_name(self, state: dict[str, Any], name: str, ignore_key: str | None = None) -> None:
        lowered = name.casefold()
        for category in self._assignable_categories(state):
            if ignore_key is None or category["key"] != ignore_key:
                if category["label"].casefold() == lowered:
                    raise RuntimeError("A category with this name already exists.")

    def _find_saved_category(self, state: dict[str, Any], category_key: str) -> dict[str, Any] | None:
        return next((category for category in state.get("categories", []) if category.get("key") == category_key), None)

    def _assignable_categories(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        return [{"key": CATEGORY_FAVORITES, "label": CATEGORY_FAVORITES}] + [category for category in state.get("categories", []) if isinstance(category, dict)]

    def _serialize_assignable_categories(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        return [{"key": category["key"], "label": category["label"], "kind": "saved", "editable": category["key"].startswith(CUSTOM_CATEGORY_PREFIX), "deletable": category["key"].startswith(CUSTOM_CATEGORY_PREFIX)} for category in self._assignable_categories(state)]

    def _build_listing_index(self, raw_categories: dict[str, Any]) -> dict[str, dict[str, Any]]:
        listing_index: dict[str, dict[str, Any]] = {}
        for category_name in SYSTEM_CATEGORY_ORDER:
            items = (raw_categories.get(category_name) or {}).get("items", [])
            for item in items:
                if isinstance(item, dict) and item.get("id") is not None:
                    listing_index[str(item["id"])] = dict(item)
        return listing_index

    def _build_result_categories(self, raw_categories: dict[str, Any], saved_categories: dict[str, Any], listing_index: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        categories = {name: self._system_category_payload(name, raw_categories) for name in SYSTEM_CATEGORY_ORDER}
        assignments = saved_categories.get("assignments", {}) if isinstance(saved_categories.get("assignments"), dict) else {}
        for category in self._assignable_categories(saved_categories):
            categories[category["key"]] = self._saved_category_payload(category, assignments, listing_index)
        return categories

    def _attach_saved_category_metadata(self, request_id: str, items: list[dict[str, Any]]) -> None:
        assignments = self._read_saved_categories(request_id).get("assignments", {})
        for item in items:
            if isinstance(item, dict) and item.get("id") is not None:
                category_keys = assignments.get(str(item["id"]), [])
                item["savedCategoryKeys"] = [key for key in category_keys if isinstance(key, str)]

    def _prune_saved_category_assignments(self, request_id: str, valid_listing_ids: set[str]) -> None:
        state = self._read_saved_categories(request_id)
        state["assignments"] = {listing_id: category_keys for listing_id, category_keys in state.get("assignments", {}).items() if listing_id in valid_listing_ids}
        self._write_saved_categories(request_id, state)

    def _valid_saved_category(self, category: Any) -> bool:
        return isinstance(category, dict) and isinstance(category.get("key"), str) and isinstance(category.get("label"), str) and category["key"].startswith(CUSTOM_CATEGORY_PREFIX) and category["label"].strip()

    def _validated_category_keys(self, state: dict[str, Any], category_keys: list[str]) -> list[str]:
        assignable_keys = {category["key"] for category in self._assignable_categories(state)}
        cleaned: list[str] = []
        seen: set[str] = set()
        for key in category_keys:
            if isinstance(key, str) and key in assignable_keys and key not in seen:
                cleaned.append(key)
                seen.add(key)
        invalid = [key for key in category_keys if not isinstance(key, str) or key not in assignable_keys]
        if invalid:
            raise KeyError(str(invalid[0]))
        return cleaned

    def _system_category_payload(self, name: str, raw_categories: dict[str, Any]) -> dict[str, Any]:
        items = (raw_categories.get(name) or {}).get("items", [])
        return {"label": name, "count": len(items) if isinstance(items, list) else 0, "items": items if isinstance(items, list) else [], "kind": "system", "editable": False, "deletable": False}

    def _saved_category_payload(self, category: dict[str, Any], assignments: dict[str, list[str]], listing_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
        items = [dict(item) for listing_id, category_keys in assignments.items() if category["key"] in category_keys for item in [listing_index.get(str(listing_id))] if item is not None]
        return {"label": category["label"], "count": len(items), "items": items, "kind": "saved", "editable": category["key"].startswith(CUSTOM_CATEGORY_PREFIX), "deletable": category["key"].startswith(CUSTOM_CATEGORY_PREFIX)}

    def _empty_results_payload(self, request_id: str, payload: dict[str, Any], page_size: int, saved_categories: dict[str, Any]) -> dict[str, Any]:
        return {"requestId": request_id, "generatedAt": payload.get("generatedAt") or utc_now(), "totalCount": payload.get("totalCount", 0), "categories": {}, "assignableCategories": self._serialize_assignable_categories(saved_categories), "items": [], "pagination": {"page": 1, "pageSize": page_size, "totalPages": 1, "totalItems": 0}, "currentCategory": None}

    def _results_payload(self, request_id: str, results_view: dict[str, Any]) -> dict[str, Any]:
        all_items = results_view["categories"][results_view["current_category"]].get("items", [])
        safe_page_size = max(1, results_view["page_size"])
        total_items = len(all_items)
        total_pages = max(1, (total_items + safe_page_size - 1) // safe_page_size)
        safe_page = min(max(1, results_view["page"]), total_pages)
        start_index = (safe_page - 1) * safe_page_size
        current_items = [dict(item) for item in all_items[start_index : start_index + safe_page_size] if isinstance(item, dict)]
        self._attach_report_cache_metadata(request_id, current_items)
        self._attach_saved_category_metadata(request_id, current_items)
        return {
            "requestId": request_id,
            "generatedAt": results_view["payload"].get("generatedAt") or utc_now(),
            "totalCount": results_view["payload"].get("totalCount", 0),
            "categories": {name: {key: value.get(key) for key in ("label", "count", "kind", "editable", "deletable")} for name, value in results_view["categories"].items()},
            "assignableCategories": self._serialize_assignable_categories(results_view["saved_categories"]),
            "currentCategory": results_view["current_category"],
            "items": current_items,
            "pagination": {"page": safe_page, "pageSize": safe_page_size, "totalPages": total_pages, "totalItems": total_items},
        }
