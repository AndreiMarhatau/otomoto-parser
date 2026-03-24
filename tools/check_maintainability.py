from __future__ import annotations

import ast
from pathlib import Path


MAX_SOURCE_LINES = 200
CHECKED_SUFFIXES = {".py", ".js", ".jsx", ".css"}
SKIP_PARTS = {"coverage", "node_modules", "dist", ".venv", "__pycache__"}
SKIP_PREFIXES = ("src/otomoto_parser.egg-info/",)


def should_check(path: Path, repo_root: Path) -> bool:
    if path.suffix not in CHECKED_SUFFIXES:
        return False
    if any(part in SKIP_PARTS for part in path.parts):
        return False
    relative = path.relative_to(repo_root).as_posix()
    if any(relative.startswith(prefix) for prefix in SKIP_PREFIXES):
        return False
    if "/tests/" in f"/{relative}/":
        return False
    if ".test." in path.name:
        return False
    return True


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    failures: list[str] = []

    for path in sorted(repo_root.rglob("*")):
        if not path.is_file() or not should_check(path, repo_root):
            continue
        with path.open("r", encoding="utf-8") as handle:
            contents = handle.read()
        line_count = contents.count("\n") + (1 if contents and not contents.endswith("\n") else 0)
        if line_count > MAX_SOURCE_LINES:
            failures.append(f"{path.relative_to(repo_root)} has {line_count} lines (max {MAX_SOURCE_LINES})")
        if path.suffix == ".py":
            failures.extend(check_python_parameters(path, repo_root, contents))

    if failures:
        print("Maintainability check failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("Maintainability check passed.")
    return 0


def check_python_parameters(path: Path, repo_root: Path, contents: str) -> list[str]:
    relative = path.relative_to(repo_root).as_posix()
    tree = ast.parse(contents, filename=str(path))
    failures: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        argument_count = len(node.args.posonlyargs) + len(node.args.args) + len(node.args.kwonlyargs)
        if node.args.vararg is not None:
            argument_count += 1
        if node.args.kwarg is not None:
            argument_count += 1
        if node.args.args and node.args.args[0].arg in {"self", "cls"}:
            argument_count -= 1
        if argument_count > 4:
            failures.append(
                f"{relative}:{node.lineno} function '{node.name}' has {argument_count} parameters (max 4)"
            )
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
