from __future__ import annotations

from pathlib import Path

from otomoto_parser.v2 import service as service_module
from otomoto_parser.v2.service import ParserAppService


def test_service_module_reexports_runtime_hooks() -> None:
    assert service_module.fetch_otomoto_vehicle_identity is not None
    assert service_module.fetch_otomoto_listing_page_data is not None
    assert service_module.VehicleHistoryClient is not None
    assert service_module.CancellationRequested is not None


def test_parser_app_service_uses_default_parser_options(tmp_path: Path) -> None:
    service = ParserAppService(tmp_path)
    try:
        assert service.parser_options["retry_attempts"] == 4
        assert service.parser_options["backoff_base"] == 1.0
        assert service.parser_options["delay_min"] == 0.0
        assert service.parser_options["delay_max"] == 0.0
        assert service.parser_options["request_timeout_s"] == 45.0
    finally:
        service.shutdown()
