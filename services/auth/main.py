import logging
import os
import sys
from contextlib import asynccontextmanager

import psycopg
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
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

MIN_KEY_BITS = 2048


def load_private_key(path: str | None) -> rsa.RSAPrivateKey:
    if not path:
        raise RuntimeError("JWT_PRIVATE_KEY_PATH is not set")
    try:
        with open(path, "rb") as f:
            key = serialization.load_pem_private_key(f.read(), password=None)
    except OSError as e:
        raise RuntimeError(f"cannot read JWT private key at {path}: {e.strerror}") from e
    except (ValueError, TypeError) as e:
        raise RuntimeError(f"JWT private key at {path} is not a valid unencrypted PEM private key") from e
    if not isinstance(key, rsa.RSAPrivateKey):
        raise RuntimeError(f"JWT private key at {path} is not an RSA key")
    if key.key_size < MIN_KEY_BITS:
        raise RuntimeError(f"JWT private key at {path} must be at least {MIN_KEY_BITS} bits")
    return key


@asynccontextmanager
async def lifespan(app):
    app.state.private_key = load_private_key(os.getenv("JWT_PRIVATE_KEY_PATH"))
    logger.info("JWT private key loaded")
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
