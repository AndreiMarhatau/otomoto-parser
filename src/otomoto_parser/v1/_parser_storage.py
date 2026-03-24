from __future__ import annotations

import json
from pathlib import Path

from ._parser_common import ParserState, _page_from_url
from ._parser_items import _item_key_from_html


def _read_state(state_path: Path) -> ParserState | None:
    if not state_path.exists():
        return None
    data = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("start_url"), str):
        return None
    next_page = data.get("next_page")
    if not isinstance(next_page, int):
        next_page = _recover_next_page(data)
        if next_page is None:
            return None
    return ParserState(
        start_url=data["start_url"],
        next_page=next_page,
        pages_completed=int(data.get("pages_completed", 0)),
        results_written=int(data.get("results_written", 0)),
        has_more=bool(data.get("has_more", True)),
    )


def _recover_next_page(data: dict) -> int | None:
    next_url = data.get("next_url")
    if not isinstance(next_url, str):
        return None
    page = _page_from_url(next_url)
    return page + 1 if bool(data.get("pending_next", False)) else page


def _write_state(state_path: Path, state: ParserState) -> None:
    state_path.write_text(
        json.dumps(
            {
                "start_url": state.start_url,
                "next_page": state.next_page,
                "pages_completed": state.pages_completed,
                "results_written": state.results_written,
                "has_more": state.has_more,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _load_existing_item_keys(output_path: Path) -> set[str]:
    if not output_path.exists():
        return set()
    keys: set[str] = set()
    for line in output_path.read_text(encoding="utf-8").splitlines():
        _collect_item_key(line, keys)
    return keys


def _collect_item_key(line: str, keys: set[str]) -> None:
    if not line.strip():
        return
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return
    item_key = record.get("item_key")
    if isinstance(item_key, str):
        keys.add(item_key)
    elif isinstance(record.get("item_id"), str):
        keys.add(f"id:{record['item_id']}")
    elif isinstance(record.get("html"), str):
        keys.add(_item_key_from_html(record["html"]))


def _append_results(
    output_path: Path,
    page_data: dict[str, object],
    *,
    seen_item_keys: set[str],
) -> tuple[int, int]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0
    with output_path.open("a", encoding="utf-8") as handle:
        for item_index, edge in enumerate(page_data["edges"]):
            written, skipped = _append_result(
                handle,
                {
                    "edge": edge,
                    "item_index": item_index,
                    "page_url": page_data["page_url"],
                    "page_number": page_data["page_number"],
                    "search_url": page_data["search_url"],
                },
                seen_item_keys,
                {"written": written, "skipped": skipped},
            )
    return written, skipped


def _append_result(handle, item_data: dict[str, object], seen_item_keys: set[str], counts: dict[str, int]) -> tuple[int, int]:
    from ._parser_items import _item_key_from_node

    edge = item_data["edge"]
    node = edge.get("node") if isinstance(edge, dict) else None
    node = node if isinstance(node, dict) else {}
    item_key, item_id = _item_key_from_node(node)
    if item_key in seen_item_keys:
        return counts["written"], counts["skipped"] + 1
    seen_item_keys.add(item_key)
    record = {
        "search_url": item_data["search_url"],
        "page_url": item_data["page_url"],
        "page_number": item_data["page_number"],
        "item_index": item_data["item_index"],
        "item_id": item_id,
        "item_key": item_key,
        "node": node,
        "edge": edge,
    }
    handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    return counts["written"] + 1, counts["skipped"]
