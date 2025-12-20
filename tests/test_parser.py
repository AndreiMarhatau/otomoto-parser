from pathlib import Path

import json

from otomoto_parser.parser import RUN_MODE_APPEND_NEWER, RUN_MODE_FULL, parse_pages


FIXTURES = Path(__file__).parent / "fixtures"


def _fixture_url(name: str) -> str:
    return (FIXTURES / name).resolve().as_uri()


def test_parse_two_pages(tmp_path: Path) -> None:
    output_path = tmp_path / "results.jsonl"
    state_path = tmp_path / "state.json"

    state = parse_pages(
        _fixture_url("page1.html"),
        output_path,
        state_path,
        retry_attempts=2,
        backoff_base=0.01,
        delay_min=0.0,
        delay_max=0.0,
    )

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert state.pages_completed == 2
    assert state.results_written == 3
    assert state.next_url.endswith("page2.html")


def test_resume_from_state(tmp_path: Path) -> None:
    output_path = tmp_path / "results.jsonl"
    state_path = tmp_path / "state.json"

    first_state = parse_pages(
        _fixture_url("page1.html"),
        output_path,
        state_path,
        max_pages=1,
        retry_attempts=2,
        backoff_base=0.01,
        delay_min=0.0,
        delay_max=0.0,
    )

    lines_after_first = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines_after_first) == 2
    assert first_state.pages_completed == 1
    assert first_state.results_written == 2

    second_state = parse_pages(
        _fixture_url("page1.html"),
        output_path,
        state_path,
        retry_attempts=2,
        backoff_base=0.01,
        delay_min=0.0,
        delay_max=0.0,
    )

    lines_after_second = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines_after_second) == 3
    assert second_state.pages_completed == 2
    assert second_state.results_written == 3


def test_custom_user_agent(tmp_path: Path) -> None:
    output_path = tmp_path / "results.jsonl"
    state_path = tmp_path / "state.json"
    custom_agent = "CustomAgent/1.0"

    parse_pages(
        _fixture_url("ua_page.html"),
        output_path,
        state_path,
        retry_attempts=2,
        backoff_base=0.01,
        delay_min=0.0,
        delay_max=0.0,
        user_agent=custom_agent,
        accept_language=None,
        locale=None,
        timezone_id=None,
    )

    record = json.loads(output_path.read_text(encoding="utf-8").splitlines()[0])
    assert custom_agent in record["html"]


def test_append_newer_stops_on_duplicate(tmp_path: Path) -> None:
    output_path = tmp_path / "results.jsonl"
    state_path = tmp_path / "state.json"

    parse_pages(
        _fixture_url("page1.html"),
        output_path,
        state_path,
        max_pages=1,
        retry_attempts=2,
        backoff_base=0.01,
        delay_min=0.0,
        delay_max=0.0,
    )

    lines_after_seed = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines_after_seed) == 2

    state = parse_pages(
        _fixture_url("page1.html"),
        output_path,
        state_path,
        run_mode=RUN_MODE_APPEND_NEWER,
        retry_attempts=2,
        backoff_base=0.01,
        delay_min=0.0,
        delay_max=0.0,
    )

    lines_after_append = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines_after_append) == 2
    assert state.pages_completed == 1


def test_full_overwrites_existing_output(tmp_path: Path) -> None:
    output_path = tmp_path / "results.jsonl"
    state_path = tmp_path / "state.json"

    parse_pages(
        _fixture_url("page1.html"),
        output_path,
        state_path,
        max_pages=1,
        retry_attempts=2,
        backoff_base=0.01,
        delay_min=0.0,
        delay_max=0.0,
    )
    assert len(output_path.read_text(encoding="utf-8").splitlines()) == 2

    state = parse_pages(
        _fixture_url("page1.html"),
        output_path,
        state_path,
        run_mode=RUN_MODE_FULL,
        retry_attempts=2,
        backoff_base=0.01,
        delay_min=0.0,
        delay_max=0.0,
    )

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert state.pages_completed == 2
