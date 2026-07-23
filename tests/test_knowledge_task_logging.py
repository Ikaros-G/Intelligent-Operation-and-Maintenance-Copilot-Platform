import ast
import logging
from pathlib import Path
import unittest


TASK_MODULE = Path(__file__).parents[1] / "app" / "tasks" / "knowledge_tasks.py"


class KnowledgeTaskLoggingTest(unittest.TestCase):
    def test_success_log_extra_does_not_overwrite_log_record_fields(self):
        tree = ast.parse(TASK_MODULE.read_text(encoding="utf-8"))
        logger_call = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "info"
        )
        extra = next(keyword.value for keyword in logger_call.keywords if keyword.arg == "extra")
        keys = [key.value for key in extra.keys]

        logging.getLogger("test").makeRecord(
            "test",
            logging.INFO,
            __file__,
            1,
            "indexed",
            (),
            None,
            extra={key: "value" for key in keys},
        )


if __name__ == "__main__":
    unittest.main()
