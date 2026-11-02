import logging
import os
import sys
import threading
from contextlib import asynccontextmanager

import consumer
import psycopg
import store
from fastapi import FastAPI, HTTPException

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=consumer.run, daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/documents")
def documents():
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, connect_timeout=10) as conn:
            # creating the table here too, so an empty database gives [] instead of an error
            store.ensure_table(conn)
            return store.list_documents(conn)
    except psycopg.OperationalError as e:
        logger.error("database unavailable: %s", e)
        raise HTTPException(status_code=503, detail="database unavailable")
