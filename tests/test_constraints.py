import ast, pathlib, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
FORBIDDEN_CALLS = ("dict", "set", "frozenset")
class TestConstraints(unittest.TestCase):
    def test_no_builtin_dict_set_collections(self):
        files = list((ROOT / "mini_redis").glob("*.py")) + [ROOT / "main.py"]
        names = [f.name for f in files]
        for expected in ["dlist.py", "hashmap.py", "minheap.py", "store.py", "parser.py", "cli.py", "main.py"]:
            self.assertIn(expected, names)                    # 검사 대상이 비어서 통과하는 일을 막는다
        problems = []
        for f in files:
            for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                if isinstance(node, (ast.Dict, ast.Set, ast.DictComp, ast.SetComp)):
                    problems.append(f"{f.name}:{node.lineno} {type(node).__name__}")
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                    problems.append(f"{f.name}:{node.lineno} {node.func.id}()")
                elif isinstance(node, ast.Import) and any("collections" in a.name for a in node.names):
                    problems.append(f"{f.name}:{node.lineno} import collections")
                elif isinstance(node, ast.ImportFrom) and node.module and "collections" in node.module:
                    problems.append(f"{f.name}:{node.lineno} from collections")
        self.assertEqual(problems, [])
