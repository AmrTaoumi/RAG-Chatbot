'''
retrieval service. Its job is to take a user's question, find the most relevant pieces 
of information in a database, and return them. It also sends an event to RabbitMQ to 
let other services know that retrieval has finished

'''
import uuid
import logging #lets application record messages about what is happening
import sys
import os 
import psycopg #to communicate with PostgreSQL databases
import json
import pika #communicating with rabbitmq
from datetime import datetime, timezone
from fastapi import FastAPI , Query, Header
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
)
logger = logging.getLogger(__name__)

app = FastAPI()

model = SentenceTransformer("all-MiniLM-L6-v2")

def embed(text): # turns text into 384 numbers
    return model.encode(text, normalize_embeddings=True).tolist()

SEARCH_SQL = """
    SELECT chunk_id, doc_id, title, url, page, text,
           1 - (embedding <=> %(v)s::vector) AS score
    FROM chunks
    ORDER BY embedding <=> %(v)s::vector, chunk_id
    LIMIT %(k)s
"""


def run_search(vector, k): #finds the closest chunks in the database
    # pgvector accepts a vector written as text
    v = "[" + ",".join(str(x) for x in vector) + "]"
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=10) as conn:
        rows = conn.execute(SEARCH_SQL, {"v": v, "k": k}).fetchall() # executes the SQL query
    return [
        {
            "chunk_id": r[0],
            "doc_id": r[1],
            "title": r[2],
            "url": r[3],
            "page": r[4],
            "text": r[5],
            "score": round(r[6], 4),
        }
        for r in rows
    ]


EXCHANGE = "rag.topic" # the exchange receives messages and routes them to matching queues
ROUTING_KEY = "retrieval.completed" # the routing key identifies the type of event being published


def publish_retrieval_completed(query, k, results, correlation_id):
    event = {
        "eventType": "RetrievalCompleted",
        "eventId": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "correlationId": correlation_id,
        "payload": {
            "query": query,
            "k": k,
            "results": [
                {
                    "chunk_id": r["chunk_id"],
                    "doc_id": r["doc_id"],
                    "title": r["title"],
                    "url": r["url"],
                    "page": r["page"],
                    "score": r["score"],
                }
                for r in results
            ],
        },
    }
    # the search result matters more than the event, so a broker problem is logged, not raised
    try:
        connection = pika.BlockingConnection(pika.URLParameters(os.environ["RABBITMQ_URL"]))
        try:
            channel = connection.channel() #opens a channel for communicating with RabbitMQ
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
        logger.warning("could not publish RetrievalCompleted: %s", e)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/search")
def search(
    q: str = Query(..., min_length=1),
    k: int = Query(5, ge=1, le=20),
    x_correlation_id: str | None = Header(None),
):
    # chat sends its correlation ID ,if it is missing this search starts a new one
    correlation_id = x_correlation_id or str(uuid.uuid4())
    results = run_search(embed(q), k)
    publish_retrieval_completed(q, k, results, correlation_id)
    return {"query": q, "results": results}