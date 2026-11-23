import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import httpx
import pika
import psycopg
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import store
from client import ask
from prompt import FALLBACK_ANSWER, build_messages, build_response

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("pika").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

RETRIEVAL_URL = os.environ.get("RETRIEVAL_URL") or "http://retrieval:8000"
TOP_K = 8
EXCHANGE = "rag.topic"
ROUTING_KEY = "answer.generated"

STATIC_DIR = Path(__file__).parent / "static"

SCORE_THRESHOLD = float( os.environ.get("SCORE_THRESHOLD") or "0.6" )

MIN_KEY_BITS = 2048

def load_public_key(path: str | None) -> rsa.RSAPublicKey:
    if not path:
        raise RuntimeError("JWT_PUBLIC_KEY_PATH is not set")
    try:
        with open(path, "rb") as f:
            key = serialization.load_pem_public_key(f.read())
    except OSError as e:
        raise RuntimeError(f"cannot read JWT public key at {path}: {e.strerror}") from e
    except ValueError as e:
        raise RuntimeError(f"JWT public key at {path} is not a valid PEM public key") from e
    if not isinstance(key, rsa.RSAPublicKey):
        raise RuntimeError(f"JWT public key at {path} is not an RSA key")
    if key.key_size < MIN_KEY_BITS:
        raise RuntimeError(f"JWT public key at {path} must be at least {MIN_KEY_BITS} bits")
    return key


@asynccontextmanager
async def lifespan(app):
    app.state.public_key = load_public_key(os.getenv("JWT_PUBLIC_KEY_PATH"))
    logger.info("JWT public key loaded")
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=10) as conn:
        store.ensure_tables(conn)
    logger.info("chat tables ready")
    yield


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class ChatRequest(BaseModel):
    question: str = Field(min_length=1)   # empty question FastAPI returns 422 


def search(question, correlation_id):
    response = httpx.get(
        f"{RETRIEVAL_URL}/search",
        params={"q": question, "k": TOP_K},
        headers={"X-Correlation-ID": correlation_id},
        timeout=30,
    )
    response.raise_for_status()          # turns 4xx/5xx into an httpx.HTTPStatusError
    return response.json()["results"]


def publish_answer_generated(question, result, correlation_id):
    event = {
        "eventType": "AnswerGenerated",
        "eventId": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "correlationId": correlation_id,
        "payload": {
            "question": question,
            "answer": result["answer"],
            "citations": result["citations"],
        },
    }
    # the answer matters more than the event so a broker problem is logged, not raised
    try:
        connection = pika.BlockingConnection(pika.URLParameters(os.environ["RABBITMQ_URL"]))
        try:
            channel = connection.channel()
            channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
            channel.basic_publish(
                exchange=EXCHANGE,
                routing_key=ROUTING_KEY,
                body=json.dumps(event),
                properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
            )
        finally:
            connection.close()
    except Exception as e:
        logger.warning("could not publish AnswerGenerated correlationId=%s error=%s", correlation_id, e)


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")

@app.post("/chat")
def chat(request: ChatRequest):
    correlation_id = str(uuid.uuid4())
    logger.info("chat request correlationId=%s", correlation_id)

    try:
        snippets = search(request.question, correlation_id)
    except httpx.HTTPError as e:
        logger.error("retrieval failed correlationId=%s error=%s", correlation_id, e)
        raise HTTPException(status_code=503, detail="retrieval unavailable")

    if not snippets or snippets[0]["score"] < SCORE_THRESHOLD:
        top_score = snippets[0]["score"] if snippets else None
        logger.info(
            "skipping LLM correlationId=%s top_score=%s threshold=%s",
            correlation_id, top_score, SCORE_THRESHOLD,
        )
        result = {"answer": FALLBACK_ANSWER, "citations": []}        
    else:
        messages = build_messages(request.question, snippets)
        try:
            answer = ask(messages)
        except (RuntimeError, ValueError) as e:
            logger.error("LLM failed correlationId=%s error=%s", correlation_id, e)
            raise HTTPException(status_code=502, detail="language model unavailable")
        result = build_response(answer, snippets)

    publish_answer_generated(request.question, result, correlation_id)
    logger.info("chat answered correlationId=%s citations=%d", correlation_id, len(result["citations"]))
    return result