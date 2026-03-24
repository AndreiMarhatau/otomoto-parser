from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIN_LINE_COVERAGE = 80.0
FRONTEND_HELPER_EXCLUSIONS = {"test-helpers.jsx"}


def main() -> int:
    args = _parse_args()
    errors = []
    if args.scope in {"all", "backend"}:
        errors.extend(_check_backend(ROOT / "coverage.json"))
    if args.scope in {"all", "frontend"}:
        errors.extend(_check_frontend(ROOT / "src/otomoto_parser/v2/frontend/coverage/coverage-summary.json"))
    if errors:
        for error in errors:
            print(error)
        return 1
    print("Per-file coverage check passed.")
    return 0


def _check_backend(path: Path) -> list[str]:
    if not path.exists():
        return [f"Missing backend coverage file: {path}"]
    data = json.loads(path.read_text(encoding="utf-8"))
    files = data.get("files", {})
    errors = []
    for source_path in _backend_source_files():
        relative_path = str(source_path.relative_to(ROOT))
        summary = files.get(relative_path, {}).get("summary")
        if summary is None:
            errors.append(f"Missing backend coverage entry for {relative_path}")
            continue
        actual = float(summary["percent_covered"])
        if actual < MIN_LINE_COVERAGE:
            errors.append(
                f"Backend per-file coverage failed for {relative_path}: "
                f"lines {actual:.2f}% < {MIN_LINE_COVERAGE:.2f}%"
            )
    return errors


def _check_frontend(path: Path) -> list[str]:
    if not path.exists():
        return [f"Missing frontend coverage file: {path}"]
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    for source_path in _frontend_source_files():
        absolute_path = str(source_path)
        summary = data.get(absolute_path)
        if summary is None:
            errors.append(f"Missing frontend coverage entry for {source_path.relative_to(ROOT)}")
            continue
        actual = float(summary["lines"]["pct"])
        if actual < MIN_LINE_COVERAGE:
            errors.append(
                f"Frontend per-file coverage failed for {source_path.relative_to(ROOT)}: "
                f"lines {actual:.2f}% < {MIN_LINE_COVERAGE:.2f}%"
            )
    return errors


def _backend_source_files() -> list[Path]:
    return sorted(
        path
        for path in (ROOT / "src/otomoto_parser").rglob("*.py")
        if "/v2/frontend/" not in str(path)
    )


def _frontend_source_files() -> list[Path]:
    frontend_root = ROOT / "src/otomoto_parser/v2/frontend/src"
    return sorted(
        path
        for path in frontend_root.rglob("*")
        if path.suffix in {".js", ".jsx"}
        and not path.name.endswith(".test.js")
        and not path.name.endswith(".test.jsx")
        and path.name not in FRONTEND_HELPER_EXCLUSIONS
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check per-file source coverage.")
    parser.add_argument(
        "--scope",
        choices=("all", "backend", "frontend"),
        default="all",
        help="Coverage scope to validate.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
