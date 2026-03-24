from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ._app_cli import build_arg_parser, frontend_dist_dir, parser_options_from_args
from ._app_frontend import mount_frontend
from ._app_geocode import geocode_location
from ._app_models import CategoryPayload, CreateRequestPayload, ListingCategoriesPayload, SettingsPayload, VehicleReportLookupPayload
from ._app_routes import register_routes
from .service import ParserAppService


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
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
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
