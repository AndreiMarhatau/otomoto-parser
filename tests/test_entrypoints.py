from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from otomoto_parser import history_report as history_report_module
from otomoto_parser.v1 import aggregation as aggregation_module
from otomoto_parser.v1 import history_report as v1_history_report
from otomoto_parser.v1._history_common import VehicleHistoryReport
from otomoto_parser.v2._app_cli import build_arg_parser, frontend_dist_dir, parser_options_from_args


def test_history_report_module_reexports_v1_api() -> None:
    assert history_report_module.fetch_vehicle_history is v1_history_report.fetch_vehicle_history
    assert history_report_module.VehicleHistoryClient is v1_history_report.VehicleHistoryClient
    assert history_report_module.VehicleHistoryReport is v1_history_report.VehicleHistoryReport
    assert history_report_module.main is v1_history_report.main


def test_aggregation_main_prints_generated_path(monkeypatch, capsys, tmp_path: Path) -> None:
    input_path = tmp_path / "results.jsonl"
    output_path = tmp_path / "report.xlsx"
    input_path.write_text("", encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["aggregation", "--input", str(input_path), "--output", str(output_path)])
    monkeypatch.setattr(aggregation_module, "generate_aggregations", lambda input_file, output_file=None: output_file or input_file)

    aggregation_module.main()

    assert capsys.readouterr().out.strip() == str(output_path)


def test_history_report_main_writes_json(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "history.json"
    report = VehicleHistoryReport(
        registration_number="WA12345",
        vin_number="VIN12345678901234",
        first_registration_date="2024-01-02",
        api_version="v1",
        technical_data={"ok": True},
        autodna_data={},
        carfax_data={},
        timeline_data={},
    )

    monkeypatch.setattr(v1_history_report, "fetch_vehicle_history", lambda *args, **kwargs: report)

    result = v1_history_report.main(
        ["WA12345", "VIN12345678901234", "2024-01-02", "--output", str(output_path)]
    )

    assert result == 0
    assert output_path.read_text(encoding="utf-8").strip() == json.dumps(asdict(report), ensure_ascii=False, indent=2)


def test_app_cli_builds_default_parser_options() -> None:
    args = build_arg_parser().parse_args([])

    assert frontend_dist_dir("/tmp/example.py") == Path("/tmp/frontend/dist")
    assert parser_options_from_args(args) == {
        "retry_attempts": 4,
        "backoff_base": 1.0,
        "delay_min": 0.0,
        "delay_max": 0.0,
        "request_timeout_s": 45.0,
    }
