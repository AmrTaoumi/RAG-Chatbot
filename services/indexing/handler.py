import json
import logging
import uuid
from datetime import datetime, timezone

import store
from chunker import chunk_pages
from embedder import embed

logger = logging.getLogger(__name__)

REQUIRED = ("doc_id", "url", "title")


class Unreadable(Exception):
    # the message can never be processed, so retrying it would not help
    pass


def handle_extracted(body, conn):
    # turns a DocumentExtracted message into the ChunksIndexed event to publish; anything
    # that is not an Unreadable error (database down, ...) is left to the caller to retry
    message = parse(body)
    payload = message["payload"]
    context = f"doc_id={payload['doc_id']} correlationId={message['correlationId']}"

    chunks = chunk_pages(payload["pages"], payload["doc_id"], payload["title"], payload["url"])
    vectors = embed([chunk["text"] for chunk in chunks])
    for chunk, vector in zip(chunks, vectors):
        # pgvector accepts a vector written as text
        chunk["embedding"] = "[" + ",".join(str(x) for x in vector) + "]"

    store.replace_chunks(conn, payload["doc_id"], chunks)
    logger.info("indexed %d chunks (%s)", len(chunks), context)

    return {
        "eventType": "ChunksIndexed",
        "eventId": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "correlationId": message["correlationId"],
        "payload": {"doc_id": payload["doc_id"], "chunk_count": len(chunks)},
    }


def parse(body):
    try:
        message = json.loads(body)
        payload = message["payload"]
        if message["eventType"] != "DocumentExtracted" or not message["correlationId"]:
            raise ValueError("not a DocumentExtracted event")
        for key in REQUIRED:
            if not isinstance(payload[key], str) or not payload[key]:
                raise ValueError(f"payload.{key} is missing")
        if not isinstance(payload["pages"], list):
            raise ValueError("payload.pages is not a list")
        for page in payload["pages"]:
            if not isinstance(page["page"], int) or not isinstance(page["text"], str):
                raise ValueError("payload.pages has a bad page")
        # two pages with one number would produce the same chunk_id and break the insert
        numbers = [page["page"] for page in payload["pages"]]
        if len(numbers) != len(set(numbers)):
            raise ValueError("payload.pages has duplicate page numbers")
    except (ValueError, KeyError, TypeError) as e:
        raise Unreadable(f"bad message: {e!r}")
    return message
