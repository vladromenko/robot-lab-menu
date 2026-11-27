"""Check the owned Python function-length and control-flow rules."""

import ast
from pathlib import Path


def violations(path: Path) -> list:
    problems = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, (ast.Break, ast.Continue)):
            problems.append(f"{path}:{node.lineno}: prohibited {type(node).__name__.lower()}")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = node.end_lineno - node.lineno + 1
            if length > 40:
                problems.append(f"{path}:{node.lineno}: {node.name} has {length} lines")
    return problems


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    paths = sorted(path for part in ("src", "tests", "scripts") for path in (root / part).rglob("*.py"))
    problems = [problem for path in paths for problem in violations(path)]
    print("\n".join(problems) if problems else f"Style gate passed for {len(paths)} Python files.")
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
