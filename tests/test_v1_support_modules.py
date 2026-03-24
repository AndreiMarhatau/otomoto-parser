from __future__ import annotations

import io
import json
import runpy
import warnings
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from otomoto_parser.v1 import _aggregation_common, _history_common, _parser_items, _parser_runner, _parser_storage
from otomoto_parser.v1._parser_common import ParserRunOptions, ParserState, RUN_MODE_FULL, RUN_MODE_RESUME
from otomoto_parser.v1.otomoto_vehicle_identity import (
    OtomotoPageRequestOptions,
    _extract_encrypted_value,
    _extract_next_data,
    _fetch_otomoto_page_html,
    _resolve_page_request_options,
    extract_otomoto_advert_from_html,
    fetch_otomoto_listing_page_data,
    fetch_otomoto_vehicle_identity,
)


def test_safe_int_covers_non_numeric_inputs() -> None:
    assert _aggregation_common.safe_int(None) is None
    assert _aggregation_common.safe_int(True) == 1
    assert _aggregation_common.safe_int(12.8) == 12
    assert _aggregation_common.safe_int(" 15.0 ") == 15
    assert _aggregation_common.safe_int("") is None
    assert _aggregation_common.safe_int("nan") is None


def test_parser_storage_reads_writes_and_collects_item_keys(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state = ParserState("https://example.invalid/search", 3, 2, 5, False)
    _parser_storage._write_state(state_path, state)
    assert _parser_storage._read_state(state_path) == state

    recovered_path = tmp_path / "recovered.json"
    recovered_path.write_text(
        json.dumps(
            {
                "start_url": "https://example.invalid/search",
                "next_url": "https://example.invalid/search?page=3",
                "pending_next": True,
            }
        ),
        encoding="utf-8",
    )
    assert _parser_storage._read_state(recovered_path) == ParserState(
        "https://example.invalid/search",
        4,
        0,
        0,
        True,
    )

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps({"start_url": 1}), encoding="utf-8")
    assert _parser_storage._read_state(invalid_path) is None

    output_path = tmp_path / "results.jsonl"
    output_path.write_text(
        "\n".join(
            [
                json.dumps({"item_key": "item-key-1"}),
                json.dumps({"item_id": "item-2"}),
                json.dumps({"html": "<article>example</article>"}),
                "{invalid",
                "",
            ]
        ),
        encoding="utf-8",
    )
    keys = _parser_storage._load_existing_item_keys(output_path)
    assert "item-key-1" in keys
    assert "id:item-2" in keys
    assert any(key.startswith("hash:") for key in keys)


def test_parser_items_cover_id_and_hash_paths() -> None:
    assert _parser_items._item_key_from_node({"id": "listing-1"}) == ("id:listing-1", "listing-1")
    item_key, item_id = _parser_items._item_key_from_node({"title": "BMW"})
    assert item_id is None
    assert item_key.startswith("hash:")
    assert _parser_items._item_key_from_html("<article>BMW</article>").startswith("hash:")


def test_parser_runner_support_helpers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output_path = tmp_path / "results.jsonl"
    state_path = tmp_path / "state.json"

    with pytest.raises(TypeError, match="output_path and state_path"):
        _parser_runner._resolve_run_paths((output_path,))

    with pytest.raises(TypeError, match="either options or legacy keyword arguments"):
        _parser_runner._resolve_run_options(ParserRunOptions(), {"retry_attempts": 1})

    output_path.write_text("seed", encoding="utf-8")
    state_path.write_text("seed", encoding="utf-8")
    normalized_url, state = _parser_runner._prepare_run(
        "https://example.invalid/search?page=2",
        output_path,
        state_path,
        RUN_MODE_FULL,
    )
    assert normalized_url == "https://example.invalid/search"
    assert state is None
    assert not output_path.exists()
    assert not state_path.exists()

    resume_state = ParserState("https://example.invalid/other", 2, 1, 1, True)
    monkeypatch.setattr(_parser_runner, "_read_state", lambda path: resume_state)
    normalized_url, state = _parser_runner._prepare_run(
        "https://example.invalid/search",
        output_path,
        state_path,
        RUN_MODE_RESUME,
    )
    assert normalized_url == "https://example.invalid/search"
    assert state is None

    monkeypatch.setattr(_parser_runner, "_load_existing_item_keys", lambda path: {"id:1"})
    context = _parser_runner._build_runtime_context(
        "https://example.invalid/search",
        output_path,
        {"state": ParserState("https://example.invalid/search", 4, 3, 2, True), "start_page": 1, "run_mode": RUN_MODE_RESUME},
        {"user_agent": "Agent/1.0", "accept_language": "pl-PL", "request_func": object()},
    )
    assert context["current_page"] == 4
    assert context["pages_completed"] == 3
    assert context["results_written"] == 2
    assert context["headers"]["User-Agent"] == "Agent/1.0"
    assert context["headers"]["accept-language"] == "pl-PL"
    assert context["seen_item_keys"] == {"id:1"}
    assert context["custom_request_func"] is True

    monkeypatch.setattr(
        _parser_runner,
        "_resolve_canonical_make_model_filters",
        lambda *args: ([{"name": "resolved", "value": "yes"}], set(), 12),
    )
    filters, page_total_count = _parser_runner._resolve_filters_if_needed(
        "https://example.invalid/search",
        [],
        {"bmw"},
        {
            "headers": {},
            "timeout_s": 10.0,
            "page_request_func": None,
            "retry_policy": SimpleNamespace(attempts=2, base_delay=0.5),
            "custom_request_func": False,
        },
    )
    assert filters == [{"name": "resolved", "value": "yes"}]
    assert page_total_count == 12

    filters, page_total_count = _parser_runner._resolve_filters_if_needed(
        "https://example.invalid/search",
        [{"name": "keep", "value": "1"}],
        {"bmw"},
        {
            "headers": {},
            "timeout_s": 10.0,
            "page_request_func": None,
            "retry_policy": SimpleNamespace(attempts=2, base_delay=0.5),
            "custom_request_func": True,
        },
    )
    assert filters == [{"name": "keep", "value": "1"}]
    assert page_total_count is None

    progress_events: list[dict[str, object]] = []
    _parser_runner._emit_start(progress_events.append, "https://example.invalid/search", context)
    assert progress_events[0]["event"] == "start"


def test_history_common_helpers_cover_error_and_abort_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _history_common._extract_api_version(
        '<link href="/nforms/api/HistoriaPojazdu/1.2.3/resource?uri=app.css" rel="stylesheet" />'
    ) == "1.2.3"
    assert _history_common._extract_api_version(
        "prefix /nforms/api/HistoriaPojazdu/9.9.9?uri=main.js suffix"
    ) == "9.9.9"
    with pytest.raises(RuntimeError, match="Could not determine"):
        _history_common._extract_api_version("missing version")

    error_without_fp = HTTPError("https://example.invalid", 500, "boom", hdrs=None, fp=None)
    assert _history_common._error_detail(error_without_fp) == "boom"

    error_with_fp = HTTPError("https://example.invalid", 500, "boom", hdrs=None, fp=io.BytesIO(b"broken"))
    assert _history_common._error_detail(error_with_fp) == "broken"

    class BrokenStream:
        def read(self) -> bytes:
            raise RuntimeError("cannot read")

        def close(self) -> None:
            return None

    error_with_broken_fp = HTTPError("https://example.invalid", 500, "boom", hdrs=None, fp=BrokenStream())
    assert _history_common._error_detail(error_with_broken_fp) == "boom"

    with pytest.raises(_history_common.CancellationRequested, match="job cancelled"):
        _history_common._abort_if_requested("job", lambda: True)

    sleep_calls: list[float] = []
    monkeypatch.setattr(_history_common.time, "sleep", lambda delay: sleep_calls.append(delay))
    _history_common._sleep_with_abort("job", 0.25, lambda: False)
    assert sleep_calls


def test_otomoto_vehicle_identity_helpers_cover_error_and_transport_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(RuntimeError, match="Could not find __NEXT_DATA__"):
        _extract_next_data("<html></html>")

    params = {
        "vin": {"values": [{"value": "secret"}]},
        "registration": {"values": [{}]},
    }
    assert _extract_encrypted_value(params, "vin") == "secret"
    assert _extract_encrypted_value(params, "missing", required=False) is None
    with pytest.raises(RuntimeError, match="Invalid encrypted"):
        _extract_encrypted_value(params, "registration")

    bad_html = '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"advert":"bad"}}}</script>'
    with pytest.raises(RuntimeError, match="Could not find advert data"):
        extract_otomoto_advert_from_html(bad_html)

    with pytest.raises(TypeError, match="either options or legacy keyword arguments"):
        _resolve_page_request_options(OtomotoPageRequestOptions(), {"timeout_s": 10.0})

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return (
                b'<script id="__NEXT_DATA__" type="application/json">'
                b'{"props":{"pageProps":{"advert":{"id":"1","parametersDict":{"vin":{"values":[{"value":"x"}]}}}}}}'
                b"</script>"
            )

    captured = {}

    def fake_urlopen(request, timeout=0):
        captured["headers"] = dict(request.header_items())
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("otomoto_parser.v1.otomoto_vehicle_identity.urlopen", fake_urlopen)
    monkeypatch.setattr(
        "otomoto_parser.v1.otomoto_vehicle_identity.extract_otomoto_vehicle_identity_from_html",
        lambda html: "identity",
    )
    monkeypatch.setattr(
        "otomoto_parser.v1.otomoto_vehicle_identity.extract_otomoto_advert_from_html",
        lambda html: {"id": "1"},
    )

    options = OtomotoPageRequestOptions(cookie_header="a=1", timeout_s=12.0)
    assert _fetch_otomoto_page_html("https://example.invalid/listing", options).startswith("<script")
    assert captured["url"] == "https://example.invalid/listing"
    assert captured["timeout"] == 12.0
    assert captured["headers"]["Cookie"] == "a=1"

    assert fetch_otomoto_vehicle_identity("https://example.invalid/listing", options=options) == "identity"
    assert fetch_otomoto_listing_page_data("https://example.invalid/listing", options=options) == {"id": "1"}


def test_main_modules_execute_entrypoints(monkeypatch: pytest.MonkeyPatch) -> None:
    root_calls: list[str] = []
    v1_calls: list[str] = []

    monkeypatch.setattr("otomoto_parser.v1.__main__.main", lambda: root_calls.append("root"))
    monkeypatch.setattr("otomoto_parser.v1.parser.main", lambda: v1_calls.append("v1"))

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        runpy.run_module("otomoto_parser.__main__", run_name="__main__")
        runpy.run_module("otomoto_parser.v1.__main__", run_name="__main__")

    assert root_calls == ["root"]
    assert v1_calls == ["v1"]
