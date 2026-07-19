import ast
import unittest
from pathlib import Path


class SocketProtocolTest(unittest.TestCase):
    def test_exposes_only_current_watching_events(self):
        source = Path("app/sockets/video_watching_socket.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        events = {
            decorator.args[0].value
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for decorator in node.decorator_list
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "on"
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
            )
        }

        self.assertEqual(events, {"connect", "disconnect", "watch_frame"})


if __name__ == "__main__":
    unittest.main()
