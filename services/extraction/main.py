import logging
import os
import sys
import threading
from contextlib import asynccontextmanager

import consumer
import psycopg
import store
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

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


class Health(BaseModel):
    status: str


class Document(BaseModel):
    doc_id: str
    title: str
    url: str
    page_count: int
    extracted_at: str


class Error(BaseModel):
    detail: str


app = FastAPI(
    title="Extraction service",
    description="Extracts per-page text from fetched PDFs and stores it in Postgres.",
    lifespan=lifespan,
)


@app.get("/health", response_model=Health, summary="Liveness check")
def health():
    return {"status": "ok"}


@app.get(
    "/documents",
    response_model=list[Document],
    summary="List extracted documents",
    description="Returns an empty list when nothing has been extracted yet.",
    responses={503: {"model": Error, "description": "database unavailable"}},
)
def documents():
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, connect_timeout=10) as conn:
            # creating the table here too, so an empty database gives [] instead of an error
            store.ensure_table(conn)
            return store.list_documents(conn)
    except psycopg.OperationalError as e:
        logger.error("database unavailable: %s", e)
        raise HTTPException(status_code=503, detail="database unavailable")
