import ast
import pathlib

SRC = pathlib.Path("src/dor")
FORBIDDEN_IMPORTS = {"dor_eval"}
FORBIDDEN_STRINGS = ("eval/", "EMSR927", "unosat")


def test_no_eval_imports():
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [n.name.split(".")[0] for n in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            assert not FORBIDDEN_IMPORTS.intersection(names), path


def test_no_eval_paths():
    for path in SRC.rglob("*.py"):
        text = path.read_text().lower()
        for s in FORBIDDEN_STRINGS:
            assert s.lower() not in text, (path, s)
