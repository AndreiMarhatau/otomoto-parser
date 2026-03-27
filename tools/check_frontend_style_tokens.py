from __future__ import annotations

import re
from pathlib import Path


FRONTEND_STYLES_DIR = Path("src/otomoto_parser/v2/frontend/src/styles")
THEME_FILE = FRONTEND_STYLES_DIR / "theme.css"
RAW_COLOR_PATTERN = re.compile(r"(#[0-9a-fA-F]{3,8}\b|rgba?\()")


def main() -> int:
    violations: list[str] = []
    for css_path in sorted(FRONTEND_STYLES_DIR.glob("*.css")):
        if css_path == THEME_FILE:
            continue
        for line_number, line in enumerate(css_path.read_text().splitlines(), start=1):
            match = RAW_COLOR_PATTERN.search(line)
            if match:
                violations.append(f"{css_path}:{line_number}: {match.group(1)}")

    if violations:
        print("Frontend style token check failed. Raw colors must live in theme.css:")
        for violation in violations:
            print(f"  - {violation}")
        return 1

    print("Frontend style token check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
