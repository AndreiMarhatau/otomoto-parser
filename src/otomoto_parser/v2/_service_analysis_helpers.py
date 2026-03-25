from __future__ import annotations

import json
import re
import threading
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..v1.history_report import CancellationRequested
from ._service_common import OPENAI_REDFLAG_MODEL, OPENAI_RESPONSES_URL


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
    payload = _request_payload(model_input)
    analysis = _parsed_analysis(_responses_request(api_key, payload))
    if cancel_event.is_set():
        raise CancellationRequested("Cancelled after the model response was received.")
    return analysis


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


def _request_payload(model_input: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": OPENAI_REDFLAG_MODEL,
        "tools": [{"type": "web_search"}],
        "reasoning": {"effort": "medium"},
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": _system_prompt()}]},
            {"role": "user", "content": [{"type": "input_text", "text": json.dumps(model_input, ensure_ascii=False)}]},
        ],
    }


def _system_prompt() -> str:
    return (
        "You analyze used-car listings and identify serious risks, notable warnings, and positive signals. "
        "Use the provided listing data first, then use web search when the VIN or other identifiers could reveal recalls, salvage history, auction history, theft reports, title issues, or other material risks. "
        "Return strict JSON with keys summary, redFlags, warnings, and greenFlags. "
        "summary must be a short string. redFlags, warnings, and greenFlags must each be arrays of short strings."
    )


def _parsed_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    parsed = _parse_analysis_json(_extract_response_output_text(payload))
    red_flags = _normalize_analysis_items(parsed, "redFlags")
    warnings = _normalize_analysis_items(parsed, "warnings")
    green_flags = _normalize_analysis_items(parsed, "greenFlags")
    summary = str(parsed.get("summary") or "").strip() or _fallback_summary(red_flags, warnings, green_flags)
    output = payload.get("output", [])
    return {
        "summary": summary,
        "redFlags": red_flags,
        "warnings": _normalize_analysis_items(parsed, "warnings"),
        "greenFlags": _normalize_analysis_items(parsed, "greenFlags"),
        "webSearchUsed": any(isinstance(item, dict) and str(item.get("type", "")).startswith("web_search") for item in output),
        "models": {"redFlags": OPENAI_REDFLAG_MODEL, "warningsAndGreenFlags": OPENAI_REDFLAG_MODEL},
    }


def _fallback_summary(red_flags: list[str], warnings: list[str], green_flags: list[str]) -> str:
    if red_flags:
        return f"{len(red_flags)} serious red flag(s) found."
    if warnings:
        return f"{len(warnings)} warning(s) need attention."
    if green_flags:
        return f"{len(green_flags)} positive signal(s) found."
    return "No serious red flags found."
