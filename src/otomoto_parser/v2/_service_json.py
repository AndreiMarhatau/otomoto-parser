from __future__ import annotations

import json
import uuid
from hashlib import sha256
from pathlib import Path
from typing import Any


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(path)


def _mask_secret(secret: str | None) -> str | None:
    if not isinstance(secret, str) or not secret:
        return None
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}...{secret[-4:]}"


def _build_report_snapshot_id(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return "missing"
    canonical = {
        "identity": payload.get("identity"),
        "report": payload.get("report"),
        "summary": payload.get("summary"),
        "retrievedAt": payload.get("retrievedAt"),
    }
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()
