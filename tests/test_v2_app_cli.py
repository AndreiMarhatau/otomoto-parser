from __future__ import annotations

from pathlib import Path

from otomoto_parser.v2._app_cli import build_arg_parser, frontend_dist_dir, parser_options_from_args


def test_frontend_dist_dir_uses_module_path() -> None:
    assert frontend_dist_dir("/tmp/example/app.py") == Path("/tmp/example/frontend/dist")


def test_build_arg_parser_and_parser_options_defaults() -> None:
    args = build_arg_parser().parse_args([])

    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.data_dir == ".parser-app-data"
    assert parser_options_from_args(args) == {
        "retry_attempts": 4,
        "backoff_base": 1.0,
        "delay_min": 0.0,
        "delay_max": 0.0,
        "request_timeout_s": 45.0,
    }
