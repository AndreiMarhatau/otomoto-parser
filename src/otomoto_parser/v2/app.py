from __future__ import annotations

import argparse
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from ..v1.parser import RUN_MODE_APPEND_NEWER, RUN_MODE_FULL, RUN_MODE_RESUME
from .service import ParserAppService


class CreateRequestPayload(BaseModel):
    url: HttpUrl


class CategoryPayload(BaseModel):
    name: str


class ListingCategoriesPayload(BaseModel):
    categoryIds: list[str]


class VehicleReportLookupPayload(BaseModel):
    registrationNumber: str
    dateFrom: str
    dateTo: str


_GEOCODE_CACHE: dict[str, dict[str, Any] | None] = {}


def geocode_location(query: str) -> dict[str, Any] | None:
    cached = _GEOCODE_CACHE.get(query)
    if cached is not None or query in _GEOCODE_CACHE:
        return cached

    request = Request(
        f"https://nominatim.openstreetmap.org/search?{urlencode({'format': 'jsonv2', 'limit': 1, 'q': query})}",
        headers={
            "User-Agent": "otomoto-parser/0.1.0",
            "Accept-Language": "en",
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError("Could not load map preview.") from exc

    if not payload:
        _GEOCODE_CACHE[query] = None
        return None
    first = payload[0]
    result = {
        "lat": float(first["lat"]),
        "lon": float(first["lon"]),
        "label": first.get("display_name") or query,
    }
    _GEOCODE_CACHE[query] = result
    return result


def frontend_dist_dir() -> Path:
    return Path(__file__).resolve().parent / "frontend" / "dist"


def create_app(
    *,
    data_dir: Path | None = None,
    service: ParserAppService | None = None,
    parser_options: dict[str, Any] | None = None,
) -> FastAPI:
    app_data_dir = data_dir or Path(".parser-app-data")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.service = service or ParserAppService(app_data_dir, parser_options=parser_options)
        try:
            yield
        finally:
            app.state.service.shutdown()

    app = FastAPI(title="Otomoto Parser App", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _service() -> ParserAppService:
        return app.state.service

    @app.get("/api/requests")
    def list_requests() -> dict[str, Any]:
        return {"items": _service().list_requests()}

    @app.post("/api/requests", status_code=201)
    def create_request_endpoint(payload: CreateRequestPayload) -> dict[str, Any]:
        request = _service().create_request(str(payload.url))
        return {"item": request}

    @app.get("/api/requests/{request_id}")
    def get_request_endpoint(request_id: str) -> dict[str, Any]:
        try:
            request = _service().get_request(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Request not found.") from exc
        return {"item": request}

    @app.delete("/api/requests/{request_id}", status_code=204)
    def delete_request_endpoint(request_id: str) -> Response:
        try:
            _service().delete_request(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Request not found.") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return Response(status_code=204)

    @app.post("/api/requests/{request_id}/categories", status_code=201)
    def create_category_endpoint(request_id: str, payload: CategoryPayload) -> dict[str, Any]:
        try:
            item = _service().create_saved_category(request_id, payload.name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Request not found.") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"item": item}

    @app.patch("/api/requests/{request_id}/categories/{category_id}")
    def rename_category_endpoint(request_id: str, category_id: str, payload: CategoryPayload) -> dict[str, Any]:
        try:
            _service().get_request(request_id)
            item = _service().rename_saved_category(request_id, category_id, payload.name)
        except KeyError as exc:
            if _service().store.get_request(request_id) is None:
                raise HTTPException(status_code=404, detail="Request not found.") from exc
            raise HTTPException(status_code=404, detail="Category not found.") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"item": item}

    @app.delete("/api/requests/{request_id}/categories/{category_id}", status_code=204)
    def delete_category_endpoint(request_id: str, category_id: str) -> Response:
        try:
            _service().get_request(request_id)
            _service().delete_saved_category(request_id, category_id)
        except KeyError as exc:
            if _service().store.get_request(request_id) is None:
                raise HTTPException(status_code=404, detail="Request not found.") from exc
            raise HTTPException(status_code=404, detail="Category not found.") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return Response(status_code=204)

    @app.put("/api/requests/{request_id}/listings/{listing_id}/categories")
    def update_listing_categories_endpoint(request_id: str, listing_id: str, payload: ListingCategoriesPayload) -> dict[str, Any]:
        try:
            request = _service().get_request(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Request not found.") from exc
        if not request["resultsReady"]:
            raise HTTPException(status_code=409, detail="Results are not ready yet.")
        try:
            item = _service().update_listing_saved_categories(request_id, listing_id, payload.categoryIds)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Listing or category not found.") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"item": item}

    @app.post("/api/requests/{request_id}/resume")
    def resume_request_endpoint(request_id: str) -> dict[str, Any]:
        try:
            mode = _service().choose_resume_mode(request_id)
            request = _service().start_run(request_id, mode)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Request not found.") from exc
        return {"item": request}

    @app.post("/api/requests/{request_id}/redo")
    def redo_request_endpoint(request_id: str) -> dict[str, Any]:
        try:
            request = _service().start_run(request_id, RUN_MODE_FULL)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Request not found.") from exc
        return {"item": request}

    @app.get("/api/requests/{request_id}/results")
    def request_results_endpoint(
        request_id: str,
        category: str | None = None,
        page: int = 1,
        page_size: int = 12,
    ) -> dict[str, Any]:
        try:
            request = _service().get_request(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Request not found.") from exc
        if not request["resultsReady"]:
            raise HTTPException(status_code=409, detail="Results are not ready yet.")
        return _service().get_results(request_id, category=category, page=page, page_size=page_size)

    @app.get("/api/requests/{request_id}/listings/{listing_id}/vehicle-report")
    def request_vehicle_report_endpoint(request_id: str, listing_id: str) -> dict[str, Any]:
        try:
            request = _service().get_request(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Request not found.") from exc
        if not request["resultsReady"]:
            raise HTTPException(status_code=409, detail="Results are not ready yet.")
        try:
            item = _service().get_vehicle_report(request_id, listing_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Listing not found.") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {"item": item}

    @app.post("/api/requests/{request_id}/listings/{listing_id}/vehicle-report/regenerate")
    def regenerate_vehicle_report_endpoint(request_id: str, listing_id: str) -> dict[str, Any]:
        try:
            request = _service().get_request(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Request not found.") from exc
        if not request["resultsReady"]:
            raise HTTPException(status_code=409, detail="Results are not ready yet.")
        try:
            item = _service().get_vehicle_report(request_id, listing_id, force_refresh=True)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Listing not found.") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {"item": item}

    @app.post("/api/requests/{request_id}/listings/{listing_id}/vehicle-report/lookup")
    def lookup_vehicle_report_endpoint(
        request_id: str,
        listing_id: str,
        payload: VehicleReportLookupPayload,
    ) -> dict[str, Any]:
        try:
            request = _service().get_request(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Request not found.") from exc
        if not request["resultsReady"]:
            raise HTTPException(status_code=409, detail="Results are not ready yet.")
        try:
            item = _service().submit_vehicle_report_lookup(
                request_id,
                listing_id,
                registration_number=payload.registrationNumber,
                date_from=payload.dateFrom,
                date_to=payload.dateTo,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Listing not found.") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"item": item}

    @app.get("/api/requests/{request_id}/excel")
    def request_excel_endpoint(request_id: str) -> FileResponse:
        try:
            request = _service().get_request(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Request not found.") from exc
        if not request["excelReady"]:
            raise HTTPException(status_code=409, detail="Excel file is not ready yet.")
        return FileResponse(
            request["excelPath"],
            filename=f"otomoto-request-{request_id}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.get("/api/geocode")
    def geocode_endpoint(query: str) -> dict[str, Any]:
        try:
            item = geocode_location(query)
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {"item": item}

    @app.post("/api/geocode/batch")
    def geocode_batch_endpoint(payload: dict[str, list[str]]) -> dict[str, Any]:
        queries = payload.get("queries", [])
        items: dict[str, Any] = {}
        for query in dict.fromkeys(query for query in queries if isinstance(query, str) and query):
            try:
                items[query] = geocode_location(query)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {"items": items}

    dist_dir = frontend_dist_dir()
    if dist_dir.exists():
        assets_dir = dist_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str) -> FileResponse:
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not found.")
            return FileResponse(dist_dir / "index.html")

    return app


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Otomoto parser UI application.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", default=".parser-app-data")
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--backoff", type=float, default=1.0)
    parser.add_argument("--delay-min", type=float, default=0.0)
    parser.add_argument("--delay-max", type=float, default=0.0)
    parser.add_argument("--request-timeout-s", type=float, default=45.0)
    return parser


def main() -> None:
    import uvicorn

    args = build_arg_parser().parse_args()
    app = create_app(
        data_dir=Path(args.data_dir),
        parser_options={
            "retry_attempts": args.retries,
            "backoff_base": args.backoff,
            "delay_min": args.delay_min,
            "delay_max": args.delay_max,
            "request_timeout_s": args.request_timeout_s,
        },
    )
    uvicorn.run(app, host=args.host, port=args.port)
