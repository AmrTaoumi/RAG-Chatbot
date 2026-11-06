import sys
from types import ModuleType
from unittest.mock import MagicMock

# the real model is a 90MB download, so tests use a stand-in  handler tests
# replace embed() with a fake that returns fixed vectors
fake = ModuleType("sentence_transformers")
fake.SentenceTransformer = MagicMock()
sys.modules.setdefault("sentence_transformers", fake)