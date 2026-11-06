import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

import httpx
import pika
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

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
TOP_K = 5
EXCHANGE = "rag.topic"
ROUTING_KEY = "answer.generated"

app = FastAPI()


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
    # the answer matters more than the event, so a broker problem is logged, not raised
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


@app.post("/chat")
def chat(request: ChatRequest):
    correlation_id = str(uuid.uuid4())
    logger.info("chat request correlationId=%s", correlation_id)

    try:
        snippets = search(request.question, correlation_id)
    except httpx.HTTPError as e:
        logger.error("retrieval failed correlationId=%s error=%s", correlation_id, e)
        raise HTTPException(status_code=503, detail="retrieval unavailable")

    if not snippets:
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