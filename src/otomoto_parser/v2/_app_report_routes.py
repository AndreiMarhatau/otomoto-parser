from __future__ import annotations

from ._app_models import VehicleReportLookupPayload


def register_report_routes(app, service_getter, ensure_results_ready, listing_service_call) -> None:
    _register_vehicle_report_routes(app, service_getter, ensure_results_ready, listing_service_call)
    _register_red_flag_routes(app, service_getter, ensure_results_ready, listing_service_call)


def _register_vehicle_report_routes(app, _service, ensure_results_ready, listing_service_call) -> None:
    @app.get("/api/requests/{request_id}/listings/{listing_id}/vehicle-report")
    def request_vehicle_report_endpoint(request_id: str, listing_id: str) -> dict:
        ensure_results_ready(_service, request_id)
        return {"item": listing_service_call(_service, request_id, lambda svc: svc.get_vehicle_report(request_id, listing_id), runtime_status=502)}

    @app.post("/api/requests/{request_id}/listings/{listing_id}/vehicle-report/regenerate")
    def regenerate_vehicle_report_endpoint(request_id: str, listing_id: str) -> dict:
        ensure_results_ready(_service, request_id)
        return {"item": listing_service_call(_service, request_id, lambda svc: svc.get_vehicle_report(request_id, listing_id, force_refresh=True), runtime_status=502)}

    @app.post("/api/requests/{request_id}/listings/{listing_id}/vehicle-report/lookup")
    def lookup_vehicle_report_endpoint(request_id: str, listing_id: str, payload: VehicleReportLookupPayload) -> dict:
        ensure_results_ready(_service, request_id)
        return {
            "item": listing_service_call(
                _service,
                request_id,
                lambda svc: svc.submit_vehicle_report_lookup(
                    request_id,
                    listing_id,
                    {
                        "registration_number": payload.registrationNumber,
                        "date_from": payload.dateFrom,
                        "date_to": payload.dateTo,
                    },
                ),
            )
        }

    @app.post("/api/requests/{request_id}/listings/{listing_id}/vehicle-report/lookup/cancel")
    def cancel_vehicle_report_lookup_endpoint(request_id: str, listing_id: str) -> dict:
        ensure_results_ready(_service, request_id)
        return {"item": listing_service_call(_service, request_id, lambda svc: svc.cancel_vehicle_report_lookup(request_id, listing_id))}


def _register_red_flag_routes(app, _service, ensure_results_ready, listing_service_call) -> None:
    @app.get("/api/requests/{request_id}/listings/{listing_id}/red-flags")
    def get_red_flag_analysis_endpoint(request_id: str, listing_id: str) -> dict:
        ensure_results_ready(_service, request_id)
        return {"item": listing_service_call(_service, request_id, lambda svc: svc.get_red_flag_analysis(request_id, listing_id), runtime_status=409)}

    @app.post("/api/requests/{request_id}/listings/{listing_id}/red-flags")
    def start_red_flag_analysis_endpoint(request_id: str, listing_id: str) -> dict:
        ensure_results_ready(_service, request_id)
        return {"item": listing_service_call(_service, request_id, lambda svc: svc.start_red_flag_analysis(request_id, listing_id))}

    @app.post("/api/requests/{request_id}/listings/{listing_id}/red-flags/cancel")
    def cancel_red_flag_analysis_endpoint(request_id: str, listing_id: str) -> dict:
        ensure_results_ready(_service, request_id)
        return {"item": listing_service_call(_service, request_id, lambda svc: svc.cancel_red_flag_analysis(request_id, listing_id))}
