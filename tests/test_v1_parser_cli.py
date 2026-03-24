from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from otomoto_parser.v1 import aggregation as aggregation_module
from otomoto_parser.v1 import _parser_cli


def test_resolve_output_paths_prefers_explicit_paths(tmp_path: Path) -> None:
    state_path = tmp_path / "custom" / "state.json"
    output_path, resolved_state_path = _parser_cli._resolve_output_paths(
        "https://www.otomoto.pl/osobowe",
        str(tmp_path / "runs"),
        None,
        str(state_path),
    )

    assert output_path == state_path.parent / "results.jsonl"
    assert resolved_state_path == state_path


def test_main_prompts_for_values_runs_parser_and_generates_aggregation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "otomoto-parser",
            "--output-dir",
            str(tmp_path / "runs"),
            "--aggregation-output",
            str(tmp_path / "report.xlsx"),
        ],
    )
    prompted_values = iter(["https://www.otomoto.pl/osobowe", "append-newer"])
    monkeypatch.setattr("builtins.input", lambda _: next(prompted_values))

    parser_call: dict[str, object] = {}
    aggregation_call: dict[str, object] = {}

    def parse_pages(url: str, output_path: Path, state_path: Path, **kwargs: object) -> SimpleNamespace:
        parser_call.update(url=url, output_path=output_path, state_path=state_path, **kwargs)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text('{"id":"listing-1"}\n', encoding="utf-8")
        return SimpleNamespace(pages_completed=2, results_written=1, next_url="https://next.example", has_more=False)

    monkeypatch.setattr(
        aggregation_module,
        "generate_aggregations",
        lambda input_file, output_file=None: aggregation_call.update(input_file=input_file, output_file=output_file),
    )

    _parser_cli.main(parse_pages)

    assert parser_call["url"] == "https://www.otomoto.pl/osobowe"
    assert parser_call["run_mode"] == "append-newer"
    assert parser_call["retry_attempts"] == 4
    assert Path(parser_call["output_path"]).exists()
    assert aggregation_call == {
        "input_file": parser_call["output_path"],
        "output_file": Path(tmp_path / "report.xlsx"),
    }
    assert '"pages_completed": 2' in capsys.readouterr().out


def test_main_rejects_unknown_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["otomoto-parser"])
    prompted_values = iter(["https://www.otomoto.pl/osobowe", "bad-mode"])
    monkeypatch.setattr("builtins.input", lambda _: next(prompted_values))

    with pytest.raises(SystemExit, match="Unknown run mode 'bad-mode'"):
        _parser_cli.main(lambda *args, **kwargs: None)


def test_main_skips_aggregation_when_disabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_path = tmp_path / "results.jsonl"
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "otomoto-parser",
            "https://www.otomoto.pl/osobowe",
            "--mode",
            "resume",
            "--output",
            str(output_path),
            "--state",
            str(state_path),
            "--no-aggregate",
        ],
    )
    generate_aggregations = pytest.fail
    monkeypatch.setattr(aggregation_module, "generate_aggregations", generate_aggregations)

    def parse_pages(url: str, parsed_output_path: Path, parsed_state_path: Path, **kwargs: object) -> SimpleNamespace:
        parsed_output_path.write_text('{"id":"listing-1"}\n', encoding="utf-8")
        assert url == "https://www.otomoto.pl/osobowe"
        assert parsed_output_path == output_path
        assert parsed_state_path == state_path
        assert kwargs["run_mode"] == "resume"
        return SimpleNamespace(pages_completed=1, results_written=1, next_url=None, has_more=False)

    _parser_cli.main(parse_pages)
