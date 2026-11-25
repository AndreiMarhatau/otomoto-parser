from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ._app_cli import build_arg_parser, frontend_dist_dir, parser_options_from_args
from ._app_frontend import mount_frontend
from ._app_geocode import geocode_location
from ._app_models import CategoryPayload, CreateRequestPayload, ListingCategoriesPayload, SettingsPayload, VehicleReportLookupPayload
from ._app_routes import register_routes
from .service import ParserAppService


async def reject_cross_origin_mutations(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        host = request.headers.get("host")
        allowed_origins = {f"{request.url.scheme}://{host}", f"https://{host}"}
        if origin and origin not in allowed_origins:
            return JSONResponse({"detail": "Cross-origin request rejected"}, status_code=403)
    return await call_next(request)


def create_app(*, data_dir: Path | None = None, service: ParserAppService | None = None, parser_options: dict[str, Any] | None = None) -> FastAPI:
    app_data_dir = data_dir or Path(".parser-app-data")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.service = service or ParserAppService(app_data_dir, parser_options=parser_options)
        try:
            yield
        finally:
            app.state.service.shutdown()

    app = FastAPI(title="Otomoto Parser App", lifespan=lifespan)
    app.middleware("http")(reject_cross_origin_mutations)
    register_routes(app)
    mount_frontend(app, frontend_dist_dir(__file__))
    return app


def main() -> None:
    import uvicorn

    args = build_arg_parser().parse_args()
    uvicorn.run(create_app(data_dir=Path(args.data_dir), parser_options=parser_options_from_args(args)), host=args.host, port=args.port)


__all__ = [
    "CategoryPayload",
    "CreateRequestPayload",
    "ListingCategoriesPayload",
    "SettingsPayload",
    "VehicleReportLookupPayload",
    "build_arg_parser",
    "create_app",
    "frontend_dist_dir",
    "geocode_location",
    "main",
]
