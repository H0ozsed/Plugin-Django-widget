"""Count the widget-related lines of code before and after the migration.

A line counts if it holds code: blank lines, comment-only lines and docstrings (any string
expression statement) are skipped, and imports are excluded on both sides. Only definitions
related to widgets are measured: profile/account endpoints exist in both versions unchanged.

    python integration/epitech/loc.py
"""

from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path

HERE = Path(__file__).resolve().parent

BEFORE = {
    "before/services/registry.py": None,  # None: every top-level statement
    "before/services/api.py": [
        "api", "about", "geocode", "weather", "forecast", "steam", "nasa_picture",
        "_is_public_url", "rss", "github", "Item_sub", "github_subscribe", "github_activity",
        "WidgetInstanceIn", "WidgetInstancePatch", "WidgetInstanceOut", "list_widgets",
        "create_widget", "update_widget", "delete_widget",
    ],
    "before/services/models.py": [
        "_fernet", "encrypt_token", "decrypt_token", "ServiceCredential", "WidgetInstance",
    ],
}  # fmt: skip

AFTER = {
    "after/services/widgets.py": None,
    "after/services/api.py": None,
    "after/epitech_after/settings.py": ["WIDGET_HUB"],
    # kept to stay compatible with the React front's pixel layout (not one-off migration code)
    "after/services/legacy.py": ["PIXEL_KEYS", "PIXEL_MAX", "pixel_position"],
}


def _name(node: ast.stmt) -> str | None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    return None


def _skipped_lines(source: str, tree: ast.Module) -> set[int]:
    skipped: set[int] = set()
    for node in ast.walk(tree):
        is_string_statement = (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
        if is_string_statement:
            skipped.update(range(node.lineno, node.end_lineno + 1))
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    code_lines = {
        line
        for tok in tokens
        if tok.type not in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
                            tokenize.DEDENT, tokenize.ENDMARKER)
        for line in range(tok.start[0], tok.end[0] + 1)
    }  # fmt: skip
    skipped.update(set(range(1, source.count("\n") + 2)) - code_lines)
    return skipped


def count(path: str, names: list[str] | None) -> int:
    """Code lines of the selected top-level statements of ``path``."""
    source = (HERE / path).read_text()
    tree = ast.parse(source)
    skipped = _skipped_lines(source, tree)
    lines: set[int] = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if names is not None and _name(node) not in names:
            continue
        start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
        lines.update(range(start, node.end_lineno + 1))
    return len(lines - skipped)


def report() -> dict[str, dict[str, int]]:
    """``{"before": {file: lines}, "after": {file: lines}}``."""
    return {
        "before": {path: count(path, names) for path, names in BEFORE.items()},
        "after": {path: count(path, names) for path, names in AFTER.items()},
    }


if __name__ == "__main__":
    for side, files in report().items():
        for path, lines in files.items():
            print(f"{side:6} {lines:4}  {path}")
        print(f"{side:6} {sum(files.values()):4}  total")
