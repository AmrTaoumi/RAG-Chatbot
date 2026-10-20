# 1. Copy services/template/ → services/<your-service>/
# 2. Add your logic to main.py
# 3. Add your dependencies to requirements.txt
# 4. Add your service block to docker-compose.yml
import logging
import sys

from fastapi import FastAPI

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
)
logger = logging.getLogger(__name__)

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}
