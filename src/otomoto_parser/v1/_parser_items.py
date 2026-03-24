from __future__ import annotations

import hashlib
import json


def _item_key_from_node(node: dict) -> tuple[str, str | None]:
    item_id = node.get("id")
    if isinstance(item_id, str) and item_id:
        return f"id:{item_id}", item_id
    payload = json.dumps(node, sort_keys=True, ensure_ascii=True)
    return f"hash:{hashlib.sha1(payload.encode('utf-8')).hexdigest()}", None


def _item_key_from_html(html: str) -> str:
    return f"hash:{hashlib.sha1(html.encode('utf-8')).hexdigest()}"
