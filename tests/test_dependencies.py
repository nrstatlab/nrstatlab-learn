"""The app boundaries of ARCHITECTURE.md §3, enforced.

An app may use another app only if the dependency graph allows it, and then only
through that app's services module (models are referred to by "app.Model" strings
in ForeignKeys, which this test also checks against the graph)."""
import ast
import re
from pathlib import Path

APPS_DIR = Path(__file__).resolve().parent.parent / "apps"
ALLOWED = {
    "core": {"study", "examinations", "papers", "progress", "accounts", "assessments"},
    "accounts": set(),
    "study": {"accounts"},
    "examinations": {"study", "progress", "accounts"},
    "papers": {"assessments", "examinations", "accounts", "progress"},
    "assessments": {"study", "progress", "accounts"},
    "progress": {"study", "accounts"},
}
# Every app may use accounts.services (the export registry and the profile flags);
# accounts itself uses no other app, so this adds no cycle.
FK_STRING = re.compile(r"""["'](core|accounts|study|examinations|papers|assessments|progress)\.[A-Z]\w+["']""")


def app_files(app):
    return [p for p in (APPS_DIR / app).rglob("*.py") if "migrations" not in p.parts]


def uses(path, own):
    """(other app, module or None) pairs this file uses."""
    found = set()
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
        elif isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        for name in names:
            parts = name.split(".")
            if parts[0] == "apps" and len(parts) > 1 and parts[1] in ALLOWED and parts[1] != own:
                found.add((parts[1], parts[2] if len(parts) > 2 else None))
    for m in FK_STRING.finditer(path.read_text()):
        if m.group(1) != own:
            found.add((m.group(1), "fk"))
    return found


def violations():
    bad = []
    for app in ALLOWED:
        for path in app_files(app):
            for other, module in uses(path, app):
                if other not in ALLOWED[app]:
                    bad.append(f"{path.relative_to(APPS_DIR)} uses {other} (not allowed for {app})")
                elif module not in (None, "services", "fk"):
                    bad.append(f"{path.relative_to(APPS_DIR)} imports {other}.{module}; use {other}.services")
    return bad


def test_apps_respect_the_dependency_graph():
    assert violations() == []


def test_the_graph_has_no_cycles():
    seen, stack = set(), set()

    def visit(n):
        assert n not in stack, f"cycle through {n}"
        if n in seen:
            return
        stack.add(n)
        for m in ALLOWED[n]:
            visit(m)
        stack.discard(n)
        seen.add(n)

    for n in ALLOWED:
        visit(n)
