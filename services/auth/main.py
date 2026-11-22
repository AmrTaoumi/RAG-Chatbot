import logging
import os
import sys
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import store

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
)
logger = logging.getLogger(__name__)


def parse_origins(raw: str | None) -> list[str]:
    origins = [o.strip().rstrip("/") for o in (raw or "").split(",") if o.strip()]
    if "*" in origins:
        raise RuntimeError("CORS_ALLOWED_ORIGINS must list explicit origins, '*' is not allowed")
    if not origins:
        raise RuntimeError("CORS_ALLOWED_ORIGINS is not set")
    return origins


ALLOWED_ORIGINS = parse_origins(os.getenv("CORS_ALLOWED_ORIGINS"))
logger.info(f"CORS allowed origins: {ALLOWED_ORIGINS}")


@asynccontextmanager
async def lifespan(app):
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=10) as conn:
        store.ensure_tables(conn)
    logger.info("auth tables ready")
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
def health():
    return {"status": "ok"}
