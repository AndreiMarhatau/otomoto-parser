from __future__ import annotations

import json
import re
import threading
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..v1.history_report import CancellationRequested
from ._service_common import OPENAI_REDFLAG_MODEL, OPENAI_REDFLAG_SUPPORTING_MODEL, OPENAI_RESPONSES_URL


def _extract_response_output_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    parts: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "\n".join(part.strip() for part in parts if part and part.strip()).strip()


def _parse_analysis_json(text: str) -> dict[str, Any]:
    if not text:
        raise RuntimeError("The OpenAI response was empty.")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise RuntimeError("The OpenAI response was not valid JSON.")
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise RuntimeError("The OpenAI response was not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("The OpenAI response JSON must be an object.")
    return payload


def _normalize_analysis_items(parsed: dict[str, Any], key: str) -> list[str]:
    raw_items = parsed.get(key, [])
    if not isinstance(raw_items, list):
        raise RuntimeError(f"The OpenAI response must contain a {key} array.")
    return [text for value in raw_items if (text := str(value).strip())]


def default_red_flag_analyzer(api_key: str, model_input: dict[str, Any], cancel_event: threading.Event) -> dict[str, Any]:
    if cancel_event.is_set():
        raise CancellationRequested("Cancelled before the model request was sent.")
    primary_payload = _red_flag_request_payload(model_input)
    payload = _responses_request(api_key, primary_payload)
    primary_analysis = _parsed_red_flag_analysis(payload)
    if cancel_event.is_set():
        raise CancellationRequested("Cancelled before the supporting model request was sent.")
    supporting_payload = _warnings_and_green_flags_request_payload(
        {
            "listingContext": model_input,
            "seriousRedFlags": primary_analysis["redFlags"],
            "summary": primary_analysis["summary"],
        }
    )
    supporting_analysis = _supporting_analysis_fallback()
    try:
        supporting_response = _responses_request(api_key, supporting_payload)
        if cancel_event.is_set():
            raise CancellationRequested("Cancelled after the model response was received.")
        supporting_analysis = _parsed_supporting_analysis(supporting_response)
    except RuntimeError:
        supporting_analysis = _supporting_analysis_fallback()
    summary = primary_analysis["summary"] or _fallback_summary(
        primary_analysis["redFlags"],
        supporting_analysis["warnings"],
        supporting_analysis["greenFlags"],
    )
    return {
        "summary": summary,
        "redFlags": primary_analysis["redFlags"],
        "warnings": supporting_analysis["warnings"],
        "greenFlags": supporting_analysis["greenFlags"],
        "webSearchUsed": bool(primary_analysis["webSearchUsed"] or supporting_analysis["webSearchUsed"]),
        "models": {"redFlags": OPENAI_REDFLAG_MODEL, "warningsAndGreenFlags": OPENAI_REDFLAG_SUPPORTING_MODEL},
    }


def _responses_request(api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI request failed with HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError(f"OpenAI request failed: {exc}") from exc


def _request_payload(
    model_input: dict[str, Any], *, model: str, system_prompt: str, tools: list[dict[str, Any]] | None, reasoning_effort: str
) -> dict[str, Any]:
    return {
        "model": model,
        "tools": tools or [],
        "reasoning": {"effort": reasoning_effort},
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": json.dumps(model_input, ensure_ascii=False)}]},
        ],
    }


def _red_flag_request_payload(model_input: dict[str, Any]) -> dict[str, Any]:
    return _request_payload(
        model_input,
        model=OPENAI_REDFLAG_MODEL,
        system_prompt=_red_flag_system_prompt(),
        tools=[{"type": "web_search"}],
        reasoning_effort="medium",
    )


def _warnings_and_green_flags_request_payload(model_input: dict[str, Any]) -> dict[str, Any]:
    return _request_payload(
        model_input,
        model=OPENAI_REDFLAG_SUPPORTING_MODEL,
        system_prompt=_warnings_and_green_flags_system_prompt(),
        tools=None,
        reasoning_effort="low",
    )


def _red_flag_system_prompt() -> str:
    return (
        "You analyze used-car listings and identify only serious, material used-car risks. "
        "Use the provided listing data first, then use web search when the VIN or other identifiers could reveal recalls, salvage history, auction history, theft reports, title issues, or other material risks. "
        "Return strict JSON with keys summary and redFlags. "
        "summary must be a short string focused on the most material risks. redFlags must be an array of short strings. "
        "Do not include warnings or green flags in this response."
    )


def _warnings_and_green_flags_system_prompt() -> str:
    return (
        "You analyze used-car listings and identify moderate warnings and positive signals. "
        "Use only the provided listing context and the supplied serious red flags summary. "
        "Return strict JSON with keys warnings and greenFlags. "
        "warnings and greenFlags must each be arrays of short strings. Do not repeat serious red flags."
    )


def _parsed_red_flag_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    parsed = _parse_analysis_json(_extract_response_output_text(payload))
    red_flags = _normalize_analysis_items(parsed, "redFlags")
    summary = str(parsed.get("summary") or "").strip() or _fallback_summary(red_flags, [], [])
    output = payload.get("output", [])
    return {
        "summary": summary,
        "redFlags": red_flags,
        "webSearchUsed": any(isinstance(item, dict) and str(item.get("type", "")).startswith("web_search") for item in output),
    }


def _parsed_supporting_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    parsed = _parse_analysis_json(_extract_response_output_text(payload))
    output = payload.get("output", [])
    return {
        "warnings": _normalize_analysis_items(parsed, "warnings"),
        "greenFlags": _normalize_analysis_items(parsed, "greenFlags"),
        "webSearchUsed": any(isinstance(item, dict) and str(item.get("type", "")).startswith("web_search") for item in output),
    }


def _supporting_analysis_fallback() -> dict[str, Any]:
    return {"warnings": [], "greenFlags": [], "webSearchUsed": False}


def _fallback_summary(red_flags: list[str], warnings: list[str], green_flags: list[str]) -> str:
    if red_flags:
        return f"{len(red_flags)} serious red flag(s) found."
    if warnings:
        return f"{len(warnings)} warning(s) need attention."
    if green_flags:
        return f"{len(green_flags)} positive signal(s) found."
    return "No serious red flags found."
