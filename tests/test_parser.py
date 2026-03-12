from pathlib import Path

import json

from otomoto_parser.parser import RUN_MODE_APPEND_NEWER, RUN_MODE_FULL, parse_pages
from otomoto_parser.v1.parser import _resolve_canonical_make_model_filters


FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_URL = (
    "https://www.otomoto.pl/osobowe/bmw/x1/seg-city-car--seg-compact--seg-sedan--seg-suv/od-2009/"
    "mazowieckie?search%5Bfilter_enum_damaged%5D=0&search%5Bfilter_enum_fuel_type%5D%5B0%5D=hybrid&"
    "search%5Bfilter_enum_fuel_type%5D%5B1%5D=petrol&search%5Bfilter_enum_fuel_type%5D%5B2%5D=plugin-hybrid&"
    "search%5Bfilter_enum_gearbox%5D=automatic&search%5Bfilter_enum_generation%5D=gen-e84-2009-2015&"
    "search%5Bfilter_enum_has_registration%5D=1&search%5Bfilter_enum_registered%5D=1&"
    "search%5Bfilter_float_mileage%3Afrom%5D=75000&search%5Bfilter_float_mileage%3Ato%5D=270000&"
    "search%5Bfilter_float_price%3Afrom%5D=25000&search%5Bfilter_float_price%3Ato%5D=40000&"
    "search%5Bfilter_float_year%3Ato%5D=2016&search%5Blat%5D=52.627&search%5Blon%5D=21.011&"
    "search%5Border%5D=created_at_first%3Adesc"
)


def _fixture_data(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _make_request(fixtures: dict[int, dict], captured_headers: list | None = None):
    def request(payload: dict, headers: dict[str, str], timeout_s: float) -> dict:
        if captured_headers is not None:
            captured_headers.append(headers)
        page = payload["variables"]["page"]
        return fixtures[page]

    return request


def _make_page_request(html: str = ""):
    def request(url: str, headers: dict[str, str], timeout_s: float) -> str:
        return html

    return request


def test_parse_two_pages(tmp_path: Path) -> None:
    output_path = tmp_path / "results.jsonl"
    state_path = tmp_path / "state.json"

    fixtures = {
        1: _fixture_data("graphql_page1.json"),
        2: _fixture_data("graphql_page2.json"),
    }

    state = parse_pages(
        SAMPLE_URL,
        output_path,
        state_path,
        retry_attempts=2,
        backoff_base=0.01,
        delay_min=0.0,
        delay_max=0.0,
        request_func=_make_request(fixtures),
        page_request_func=_make_page_request(),
    )

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert state.pages_completed == 2
    assert state.results_written == 3
    assert "page=2" in state.next_url


def test_resume_from_state(tmp_path: Path) -> None:
    output_path = tmp_path / "results.jsonl"
    state_path = tmp_path / "state.json"

    fixtures = {
        1: _fixture_data("graphql_page1.json"),
        2: _fixture_data("graphql_page2.json"),
    }

    first_state = parse_pages(
        SAMPLE_URL,
        output_path,
        state_path,
        max_pages=1,
        retry_attempts=2,
        backoff_base=0.01,
        delay_min=0.0,
        delay_max=0.0,
        request_func=_make_request(fixtures),
        page_request_func=_make_page_request(),
    )

    lines_after_first = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines_after_first) == 2
    assert first_state.pages_completed == 1
    assert first_state.results_written == 2

    second_state = parse_pages(
        SAMPLE_URL,
        output_path,
        state_path,
        retry_attempts=2,
        backoff_base=0.01,
        delay_min=0.0,
        delay_max=0.0,
        request_func=_make_request(fixtures),
        page_request_func=_make_page_request(),
    )

    lines_after_second = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines_after_second) == 3
    assert second_state.pages_completed == 2
    assert second_state.results_written == 3


def test_custom_user_agent(tmp_path: Path) -> None:
    output_path = tmp_path / "results.jsonl"
    state_path = tmp_path / "state.json"
    custom_agent = "CustomAgent/1.0"

    fixtures = {1: _fixture_data("graphql_page1.json")}
    captured_headers: list[dict[str, str]] = []

    parse_pages(
        SAMPLE_URL,
        output_path,
        state_path,
        max_pages=1,
        retry_attempts=2,
        backoff_base=0.01,
        delay_min=0.0,
        delay_max=0.0,
        user_agent=custom_agent,
        accept_language=None,
        request_func=_make_request(fixtures, captured_headers),
        page_request_func=_make_page_request(),
    )

    assert captured_headers
    assert captured_headers[0]["User-Agent"] == custom_agent


def test_append_newer_stops_on_duplicate(tmp_path: Path) -> None:
    output_path = tmp_path / "results.jsonl"
    state_path = tmp_path / "state.json"

    fixtures = {1: _fixture_data("graphql_page1.json")}

    parse_pages(
        SAMPLE_URL,
        output_path,
        state_path,
        max_pages=1,
        retry_attempts=2,
        backoff_base=0.01,
        delay_min=0.0,
        delay_max=0.0,
        request_func=_make_request(fixtures),
        page_request_func=_make_page_request(),
    )

    lines_after_seed = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines_after_seed) == 2

    state = parse_pages(
        SAMPLE_URL,
        output_path,
        state_path,
        run_mode=RUN_MODE_APPEND_NEWER,
        retry_attempts=2,
        backoff_base=0.01,
        delay_min=0.0,
        delay_max=0.0,
        request_func=_make_request(fixtures),
        page_request_func=_make_page_request(),
    )

    lines_after_append = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines_after_append) == 2
    assert state.pages_completed == 1


def test_full_overwrites_existing_output(tmp_path: Path) -> None:
    output_path = tmp_path / "results.jsonl"
    state_path = tmp_path / "state.json"

    fixtures = {
        1: _fixture_data("graphql_page1.json"),
        2: _fixture_data("graphql_page2.json"),
    }

    parse_pages(
        SAMPLE_URL,
        output_path,
        state_path,
        max_pages=1,
        retry_attempts=2,
        backoff_base=0.01,
        delay_min=0.0,
        delay_max=0.0,
        request_func=_make_request(fixtures),
        page_request_func=_make_page_request(),
    )
    assert len(output_path.read_text(encoding="utf-8").splitlines()) == 2

    state = parse_pages(
        SAMPLE_URL,
        output_path,
        state_path,
        run_mode=RUN_MODE_FULL,
        retry_attempts=2,
        backoff_base=0.01,
        delay_min=0.0,
        delay_max=0.0,
        request_func=_make_request(fixtures),
        page_request_func=_make_page_request(),
    )

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert state.pages_completed == 2


def test_start_page_from_url(tmp_path: Path) -> None:
    output_path = tmp_path / "results.jsonl"
    state_path = tmp_path / "state.json"

    fixtures = {2: _fixture_data("graphql_page2.json")}

    parse_pages(
        f"{SAMPLE_URL}&page=2",
        output_path,
        state_path,
        max_pages=1,
        retry_attempts=2,
        backoff_base=0.01,
        delay_min=0.0,
        delay_max=0.0,
        request_func=_make_request(fixtures),
        page_request_func=_make_page_request(),
    )

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


def test_resolve_canonical_model_filter_value() -> None:
    filters = [
        {"name": "category_id", "value": "29"},
        {"name": "filter_enum_make", "value": "mercedes-benz"},
        {"name": "filter_enum_model", "value": "cla-klasa"},
    ]

    def page_request(url: str, headers: dict[str, str], timeout_s: float) -> str:
        assert "mercedes-benz/cla-klasa" in url
        return (
            '<script id="__NEXT_DATA__" type="application/json">'
            '{"props":{"pageProps":{"cache":{"listing":"{\\"advertSearch\\":{\\"appliedFilters\\":['
            '{\\"name\\":\\"filter_enum_make\\",\\"value\\":\\"mercedes-benz\\",\\"canonical\\":\\"mercedes-benz\\"},'
            '{\\"name\\":\\"filter_enum_model\\",\\"value\\":\\"cla\\",\\"canonical\\":\\"cla-klasa\\"}'
            ']}}"}}}}</script>'
        )

    resolved, fetch_failed, total_count = _resolve_canonical_make_model_filters(
        "https://www.otomoto.pl/osobowe/mercedes-benz/cla-klasa",
        filters,
        headers={},
        timeout_s=1.0,
        page_request_func=page_request,
    )

    assert fetch_failed is False
    assert total_count is None
    assert resolved[1]["value"] == "mercedes-benz"
    assert resolved[2]["value"] == "cla"
