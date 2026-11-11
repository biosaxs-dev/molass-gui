"""Every ``command=self._x`` of a view's buttons and every ``self._x(...)`` call must name a method of the class:
a dropped ``def`` line only shows when the button is clicked (QuickView lost ``_show_continuity`` once)."""
import ast
import pathlib

import pytest

VIEWS = ["naive_view", "quick_view", "upgraded_view", "rigorous_view"]


@pytest.mark.parametrize("name", VIEWS)
def test_view_commands_and_calls_resolve_to_methods(name):
    path = pathlib.Path(__file__).resolve().parent.parent / "molass_gui" / f"{name}.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
        defined = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
        called = {n.func.attr for n in ast.walk(cls) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and isinstance(n.func.value, ast.Name) and n.func.value.id == "self"}
        commands = {kw.value.attr for n in ast.walk(cls) if isinstance(n, ast.Call) for kw in n.keywords
                    if kw.arg == "command" and isinstance(kw.value, ast.Attribute)
                    and isinstance(kw.value.value, ast.Name) and kw.value.value.id == "self"}
        # attributes assigned in the class (callbacks kept in self._x = ...) are not methods
        assigned = {t.attr for n in ast.walk(cls) if isinstance(n, ast.Assign) for t in n.targets
                    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self"}
        missing = sorted((called | commands) - defined - assigned)
        assert not missing, f"{cls.name} has no method {missing}"
