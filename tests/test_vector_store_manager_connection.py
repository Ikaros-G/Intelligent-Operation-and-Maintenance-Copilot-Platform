import importlib.util
from pathlib import Path
import sys
import types
import unittest


MODULE_PATH = Path(__file__).parents[1] / "app" / "services" / "vector_store_manager.py"


class VectorStoreManagerConnectionTest(unittest.TestCase):
    def test_langchain_milvus_uses_explicit_container_uri(self):
        captured = {}

        class FakeMilvus:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        class FakeMilvusManager:
            def connect(self):
                return object()

        fake_modules = {
            "langchain_core": types.ModuleType("langchain_core"),
            "langchain_core.documents": types.SimpleNamespace(Document=object),
            "langchain_milvus": types.SimpleNamespace(Milvus=FakeMilvus),
            "loguru": types.SimpleNamespace(
                logger=types.SimpleNamespace(info=lambda *args: None, error=lambda *args: None)
            ),
            "app.config": types.SimpleNamespace(
                config=types.SimpleNamespace(milvus_host="standalone", milvus_port=19530)
            ),
            "app.core.milvus_client": types.SimpleNamespace(
                milvus_manager=FakeMilvusManager()
            ),
            "app.services.vector_embedding_service": types.SimpleNamespace(
                vector_embedding_service=object()
            ),
        }

        previous = {name: sys.modules.get(name) for name in fake_modules}
        sys.modules.update(fake_modules)
        try:
            spec = importlib.util.spec_from_file_location("vector_store_manager_test", MODULE_PATH)
            module = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(module)
        finally:
            for name, old_module in previous.items():
                if old_module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = old_module

        self.assertEqual(
            captured["connection_args"],
            {"uri": "http://standalone:19530"},
        )


if __name__ == "__main__":
    unittest.main()
