from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def register_geocode_routes(app) -> None:
    @app.get("/api/geocode")
    def geocode_endpoint(query: str) -> dict:
        from . import app as app_module

        try:
            return {"item": app_module.geocode_location(query)}
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/api/geocode/batch")
    def geocode_batch_endpoint(payload: dict[str, list[str]]) -> dict:
        from . import app as app_module

        items: dict[str, object] = {}
        queries = dict.fromkeys(query for query in payload.get("queries", []) if isinstance(query, str) and query)
        for query in queries:
            try:
                items[query] = app_module.geocode_location(query)
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {"items": items}


def mount_frontend(app, dist_dir) -> None:
    if not dist_dir.exists():
        return
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found.")
        return FileResponse(dist_dir / "index.html")
