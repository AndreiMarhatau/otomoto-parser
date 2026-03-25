from __future__ import annotations

import io
import json
import threading
from urllib.error import HTTPError, URLError

import pytest

from otomoto_parser.v1.history_report import CancellationRequested
from otomoto_parser.v2 import _service_analysis_helpers as helpers


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_request_payload_contains_expected_model_tools_and_input() -> None:
    payload = helpers._red_flag_request_payload({"listingId": "abc", "notes": {"vehicleReportReady": True}})

    assert payload["model"] == "gpt-5.4"
    assert payload["tools"] == [{"type": "web_search"}]
    assert payload["reasoning"] == {"effort": "medium"}
    assert payload["input"][0]["role"] == "system"
    assert "strict JSON" in payload["input"][0]["content"][0]["text"]
    assert json.loads(payload["input"][1]["content"][0]["text"]) == {"listingId": "abc", "notes": {"vehicleReportReady": True}}


def test_supporting_request_payload_uses_mini_model_without_tools() -> None:
    payload = helpers._warnings_and_green_flags_request_payload({"listingId": "abc", "seriousRedFlags": ["damage"]})

    assert payload["model"] == "gpt-5.4-mini"
    assert payload["tools"] == []
    assert payload["reasoning"] == {"effort": "low"}
    assert payload["input"][0]["role"] == "system"
    assert "warnings and greenFlags" in payload["input"][0]["content"][0]["text"]
    assert json.loads(payload["input"][1]["content"][0]["text"]) == {"listingId": "abc", "seriousRedFlags": ["damage"]}


def test_extract_and_parse_red_flag_json_from_nested_output() -> None:
    payload = {
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": 'prefix {"summary":"Needs review","redFlags":[" damage "]} suffix',
                    }
                ],
            },
            {"type": "web_search_call"},
        ]
    }

    parsed = helpers._parsed_red_flag_analysis(payload)

    assert parsed == {
        "summary": "Needs review",
        "redFlags": ["damage"],
        "webSearchUsed": True,
    }


def test_extract_and_parse_supporting_json_from_nested_output() -> None:
    payload = {
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": 'prefix {"warnings":[" docs "],"greenFlags":["service history"]} suffix',
                    }
                ],
            },
        ]
    }

    parsed = helpers._parsed_supporting_analysis(payload)

    assert parsed == {
        "warnings": ["docs"],
        "greenFlags": ["service history"],
        "webSearchUsed": False,
    }


def test_parsed_analysis_uses_fallback_summary_when_missing() -> None:
    parsed = helpers._parsed_red_flag_analysis({"output_text": '{"redFlags":["auction history"]}'})

    assert parsed["summary"] == "1 serious red flag(s) found."
    assert parsed["redFlags"] == ["auction history"]


def test_parse_analysis_json_rejects_invalid_content() -> None:
    with pytest.raises(RuntimeError, match="not valid JSON"):
        helpers._parse_analysis_json("not-json")

    with pytest.raises(RuntimeError, match="must be an object"):
        helpers._parse_analysis_json('["not","an","object"]')

    with pytest.raises(RuntimeError, match="greenFlags array"):
        helpers._parsed_supporting_analysis({"output_text": '{"warnings":[],"greenFlags":"bad"}'})


def test_default_red_flag_analyzer_raises_http_error_with_body(monkeypatch) -> None:
    cancel_event = threading.Event()
    error = HTTPError(
        helpers.OPENAI_RESPONSES_URL,
        400,
        "bad request",
        hdrs=None,
        fp=io.BytesIO(b'{"error":"invalid"}'),
    )

    monkeypatch.setattr(helpers, "urlopen", lambda request, timeout=0: (_ for _ in ()).throw(error))

    with pytest.raises(RuntimeError, match='HTTP 400: {"error":"invalid"}'):
        helpers.default_red_flag_analyzer("key", {"listingId": "abc"}, cancel_event)


def test_default_red_flag_analyzer_raises_runtime_error_for_transport_failure(monkeypatch) -> None:
    cancel_event = threading.Event()
    monkeypatch.setattr(helpers, "urlopen", lambda request, timeout=0: (_ for _ in ()).throw(URLError("offline")))

    with pytest.raises(RuntimeError, match="OpenAI request failed:"):
        helpers.default_red_flag_analyzer("key", {"listingId": "abc"}, cancel_event)


def test_default_red_flag_analyzer_honors_cancellation_before_and_after_request(monkeypatch) -> None:
    cancel_event = threading.Event()
    cancel_event.set()
    with pytest.raises(CancellationRequested, match="before the model request"):
        helpers.default_red_flag_analyzer("key", {"listingId": "abc"}, cancel_event)

    after_response_event = threading.Event()

    def fake_urlopen(request, timeout=0):
        after_response_event.set()
        return _FakeResponse({"output_text": '{"summary":"ok","redFlags":[]}'})

    monkeypatch.setattr(helpers, "urlopen", fake_urlopen)
    cancelling_event = threading.Event()

    def set_after_response(*args, **kwargs):
        result = fake_urlopen(*args, **kwargs)
        cancelling_event.set()
        return result

    monkeypatch.setattr(helpers, "urlopen", set_after_response)

    with pytest.raises(CancellationRequested, match="before the supporting model request"):
        helpers.default_red_flag_analyzer("key", {"listingId": "abc"}, cancelling_event)


def test_default_red_flag_analyzer_returns_normalized_payload(monkeypatch) -> None:
    responses = iter(
        [
            _FakeResponse(
                {
                    "output_text": '{"summary":" Clean ","redFlags":[" salvage "]}',
                    "output": [{"type": "web_search_preview"}],
                }
            ),
            _FakeResponse(
                {
                    "output_text": '{"warnings":[" docs "],"greenFlags":[" one-owner "]}',
                }
            ),
        ]
    )
    monkeypatch.setattr(helpers, "urlopen", lambda request, timeout=0: next(responses))

    result = helpers.default_red_flag_analyzer("key", {"listingId": "abc"}, threading.Event())

    assert result == {
        "summary": "Clean",
        "redFlags": ["salvage"],
        "warnings": ["docs"],
        "greenFlags": ["one-owner"],
        "webSearchUsed": True,
        "models": {"redFlags": "gpt-5.4", "warningsAndGreenFlags": "gpt-5.4-mini"},
    }


def test_default_red_flag_analyzer_falls_back_when_supporting_request_fails(monkeypatch) -> None:
    responses = iter(
        [
            _FakeResponse(
                {
                    "output_text": '{"summary":"Primary only","redFlags":["salvage"]}',
                    "output": [{"type": "web_search_preview"}],
                }
            ),
            RuntimeError("supporting failed"),
        ]
    )

    def fake_urlopen(request, timeout=0):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(helpers, "urlopen", fake_urlopen)

    result = helpers.default_red_flag_analyzer("key", {"listingId": "abc"}, threading.Event())

    assert result == {
        "summary": "Primary only",
        "redFlags": ["salvage"],
        "warnings": [],
        "greenFlags": [],
        "webSearchUsed": True,
        "models": {"redFlags": "gpt-5.4", "warningsAndGreenFlags": "gpt-5.4-mini"},
    }


def test_default_red_flag_analyzer_falls_back_when_supporting_response_is_malformed(monkeypatch) -> None:
    responses = iter(
        [
            _FakeResponse({"output_text": '{"summary":"Primary only","redFlags":["salvage"]}'}),
            _FakeResponse({"output_text": '{"warnings":"bad","greenFlags":[]}'}),
        ]
    )
    monkeypatch.setattr(helpers, "urlopen", lambda request, timeout=0: next(responses))

    result = helpers.default_red_flag_analyzer("key", {"listingId": "abc"}, threading.Event())

    assert result == {
        "summary": "Primary only",
        "redFlags": ["salvage"],
        "warnings": [],
        "greenFlags": [],
        "webSearchUsed": False,
        "models": {"redFlags": "gpt-5.4", "warningsAndGreenFlags": "gpt-5.4-mini"},
    }


def test_default_red_flag_analyzer_honors_cancellation_before_supporting_request(monkeypatch) -> None:
    calls: list[str] = []
    cancel_event = threading.Event()

    def fake_urlopen(request, timeout=0):
        payload = json.loads(request.data.decode("utf-8"))
        calls.append(payload["model"])
        if payload["model"] == "gpt-5.4":
            cancel_event.set()
            return _FakeResponse({"output_text": '{"summary":"ok","redFlags":[]}'})
        raise AssertionError("supporting request should not be sent after cancellation")

    monkeypatch.setattr(helpers, "urlopen", fake_urlopen)

    with pytest.raises(CancellationRequested, match="before the supporting model request"):
        helpers.default_red_flag_analyzer("key", {"listingId": "abc"}, cancel_event)

    assert calls == ["gpt-5.4"]
