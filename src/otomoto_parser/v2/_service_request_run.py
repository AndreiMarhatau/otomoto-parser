from __future__ import annotations


from ..v1.aggregation import generate_aggregations
from ..v1.parser import RUN_MODE_FULL
from ._service_common import REQUEST_STATUS_CATEGORIZING, REQUEST_STATUS_FAILED, REQUEST_STATUS_READY, REQUEST_STATUS_RUNNING
from ._service_json import _write_json
from ._service_listing_helpers import build_categorized_payload


class ServiceRunMixin:
    def _update_progress(self, request_id: str, payload: dict) -> None:
        event = payload.get("event")
        if event == "page_fetch_started":
            self.store.update_request(request_id, status=REQUEST_STATUS_RUNNING, progressMessage=f"Fetching page {payload['page']}...", pagesCompleted=payload["pages_completed"], resultsWritten=payload["results_written"])
        elif event == "page_fetch_finished":
            state = payload["state"]
            self.store.update_request(request_id, status=REQUEST_STATUS_RUNNING, progressMessage=f"Fetched page {payload['page']} ({payload['written']} new listings).", pagesCompleted=state["pages_completed"], resultsWritten=state["results_written"])
        elif event == "complete":
            state = payload["state"]
            self.store.update_request(request_id, status=REQUEST_STATUS_CATEGORIZING, progressMessage="Categorizing listings and generating Excel output.", pagesCompleted=state["pages_completed"], resultsWritten=state["results_written"], hasMore=state["has_more"])

    def _run_request(self, request_id: str, mode: str) -> None:
        request = self.get_request(request_id)
        paths = self.request_paths(request_id)
        paths.request_dir.mkdir(parents=True, exist_ok=True)
        if mode == RUN_MODE_FULL:
            for path in (paths.categorized_path, paths.excel_path):
                if path.exists():
                    path.unlink()
        try:
            self.store.update_request(request_id, status=REQUEST_STATUS_RUNNING, progressMessage="Starting parser.", error=None)
            self.parser_runner(request["sourceUrl"], paths.results_path, paths.state_path, run_mode=mode, progress_callback=lambda payload: self._update_progress(request_id, payload), **self.parser_options)
            if not paths.results_path.exists():
                raise RuntimeError("Parser finished without any results.")
            generate_aggregations(paths.results_path, paths.excel_path)
            categorized = build_categorized_payload(paths.results_path)
            if mode == RUN_MODE_FULL:
                valid_listing_ids = {str(item.get("id")) for category in categorized.get("categories", {}).values() if isinstance(category, dict) for item in category.get("items", []) if isinstance(item, dict) and item.get("id") is not None}
                with self._request_lock(request_id):
                    self._prune_saved_category_assignments(request_id, valid_listing_ids)
            _write_json(paths.categorized_path, categorized)
            self.store.update_request(request_id, status=REQUEST_STATUS_READY, progressMessage=f"Ready. {categorized['totalCount']} listings categorized.", resultsReady=True, excelReady=paths.excel_path.exists())
        except Exception as exc:
            self.store.update_request(request_id, status=REQUEST_STATUS_FAILED, progressMessage="Request failed.", error=str(exc))
        finally:
            with self._lock:
                self._futures.pop(request_id, None)
