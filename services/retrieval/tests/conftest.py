import os
import sys
import types
from pathlib import Path

# retrieval loads the embedding model at import time; tests use a fake so no download is needed
fake = types.ModuleType("sentence_transformers")


class FakeModel:
    def __init__(self, *a, **kw):
        pass

    def encode(self, text, **kw):
        class V:
            def tolist(self):
                return [0.1] * 384

        return V()


fake.SentenceTransformer = FakeModel
sys.modules["sentence_transformers"] = fake
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://x:x@localhost:5432/x")
os.environ.setdefault("RABBITMQ_URL", "amqp://x:x@localhost:5672/")
