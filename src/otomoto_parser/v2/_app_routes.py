from __future__ import annotations

from fastapi import HTTPException, Response
from fastapi.responses import FileResponse

from ..v1.parser import RUN_MODE_FULL
from ._app_frontend import register_geocode_routes
from ._app_report_routes import register_report_routes
from ._app_models import CategoryPayload, CreateRequestPayload, ListingCategoriesPayload, SettingsPayload


def register_routes(app) -> None:
    def _service():
        return app.state.service

    _register_request_routes(app, _service)
    _register_category_routes(app, _service)
    _register_listing_category_routes(app, _service)
    _register_run_routes(app, _service)
    _register_results_routes(app, _service)
    register_report_routes(app, _service, _ensure_results_ready, _listing_service_call)
    register_geocode_routes(app)

def _register_request_routes(app, _service) -> None:
    @app.get("/api/requests")
    def list_requests() -> dict:
        return {"items": _service().list_requests()}

    @app.get("/api/settings")
    def get_settings_endpoint() -> dict:
        return {"item": _service().get_settings()}

    @app.put("/api/settings")
    def update_settings_endpoint(payload: SettingsPayload) -> dict:
        return {"item": _service().update_settings(openai_api_key=payload.openaiApiKey)}

    @app.post("/api/requests", status_code=201)
    def create_request_endpoint(payload: CreateRequestPayload) -> dict:
        return {"item": _service().create_request(str(payload.url))}

    @app.get("/api/requests/{request_id}")
    def get_request_endpoint(request_id: str) -> dict:
        return {"item": _request_or_404(_service, request_id)}

    @app.delete("/api/requests/{request_id}", status_code=204)
    def delete_request_endpoint(request_id: str) -> Response:
        try:
            _service().delete_request(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Request not found.") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return Response(status_code=204)

def _register_category_routes(app, _service) -> None:
    @app.post("/api/requests/{request_id}/categories", status_code=201)
    def create_category_endpoint(request_id: str, payload: CategoryPayload) -> dict:
        return {"item": _service_call(_service, lambda svc: svc.create_saved_category(request_id, payload.name), not_found="Request not found.")}

    @app.patch("/api/requests/{request_id}/categories/{category_id}")
    def rename_category_endpoint(request_id: str, category_id: str, payload: CategoryPayload) -> dict:
        return {"item": _rename_category(_service(), request_id, category_id, payload.name)}

    @app.delete("/api/requests/{request_id}/categories/{category_id}", status_code=204)
    def delete_category_endpoint(request_id: str, category_id: str) -> Response:
        _delete_category(_service(), request_id, category_id)
        return Response(status_code=204)

def _register_listing_category_routes(app, _service) -> None:
    @app.put("/api/requests/{request_id}/listings/{listing_id}/categories")
    def update_listing_categories_endpoint(request_id: str, listing_id: str, payload: ListingCategoriesPayload) -> dict:
        _ensure_results_ready(_service, request_id)
        try:
            item = _service().update_listing_saved_categories(request_id, listing_id, payload.categoryIds)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Listing or category not found.") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"item": item}

def _register_run_routes(app, _service) -> None:
    @app.post("/api/requests/{request_id}/resume")
    def resume_request_endpoint(request_id: str) -> dict:
        svc = _service()
        try:
            return {"item": svc.start_run(request_id, svc.choose_resume_mode(request_id))}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Request not found.") from exc

    @app.post("/api/requests/{request_id}/redo")
    def redo_request_endpoint(request_id: str) -> dict:
        return {"item": _service_call(_service, lambda svc: svc.start_run(request_id, RUN_MODE_FULL), not_found="Request not found.")}

def _register_results_routes(app, _service) -> None:
    @app.get("/api/requests/{request_id}/results")
    def request_results_endpoint(request_id: str, category: str | None = None, page: int = 1, page_size: int = 12) -> dict:
        _ensure_results_ready(_service, request_id)
        return _service().get_results(request_id, category=category, page=page, page_size=page_size)

    @app.get("/api/requests/{request_id}/excel")
    def request_excel_endpoint(request_id: str) -> FileResponse:
        request = _request_or_404(_service, request_id)
        if not request["excelReady"]:
            raise HTTPException(status_code=409, detail="Excel file is not ready yet.")
        return FileResponse(request["excelPath"], filename=f"otomoto-request-{request_id}.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def _request_or_404(_service, request_id: str) -> dict:
    try:
        return _service().get_request(request_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Request not found.") from exc

def _ensure_results_ready(_service, request_id: str) -> dict:
    request = _request_or_404(_service, request_id)
    if not request["resultsReady"]:
        raise HTTPException(status_code=409, detail="Results are not ready yet.")
    return request

def _service_call(_service, callback, *, not_found: str, runtime_status: int = 409):
    try:
        return callback(_service())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=not_found) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=runtime_status, detail=str(exc)) from exc

def _listing_service_call(_service, request_id: str, callback, *, runtime_status: int = 409):
    try:
        return callback(_service())
    except KeyError as exc:
        if _service().store.get_request(request_id) is None:
            raise HTTPException(status_code=404, detail="Request not found.") from exc
        raise HTTPException(status_code=404, detail="Listing not found.") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=runtime_status, detail=str(exc)) from exc


def _rename_category(service, request_id: str, category_id: str, name: str) -> dict:
    try:
        service.get_request(request_id)
        return service.rename_saved_category(request_id, category_id, name)
    except KeyError as exc:
        _raise_category_not_found(service, request_id, exc)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _delete_category(service, request_id: str, category_id: str) -> None:
    try:
        service.get_request(request_id)
        service.delete_saved_category(request_id, category_id)
    except KeyError as exc:
        _raise_category_not_found(service, request_id, exc)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _raise_category_not_found(service, request_id: str, exc: KeyError) -> None:
    if service.store.get_request(request_id) is None:
        raise HTTPException(status_code=404, detail="Request not found.") from exc
    raise HTTPException(status_code=404, detail="Category not found.") from exc
