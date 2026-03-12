from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from ..v1.parser import RUN_MODE_APPEND_NEWER, RUN_MODE_FULL, RUN_MODE_RESUME
from .service import ParserAppService


class CreateRequestPayload(BaseModel):
    url: HttpUrl


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
    def request_results_endpoint(request_id: str) -> dict[str, Any]:
        try:
            request = _service().get_request(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Request not found.") from exc
        if not request["resultsReady"]:
            raise HTTPException(status_code=409, detail="Results are not ready yet.")
        return _service().get_results(request_id)

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
