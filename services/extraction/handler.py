import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import store
from extractor import extract_pages

logger = logging.getLogger(__name__)

PDF_DIR = Path(os.environ.get("PDF_DIR", "/data/pdfs"))
REQUIRED = ("doc_id", "url", "title", "path")


class Unreadable(Exception):
    # the message can never be processed, so retrying it would not help
    pass


def handle_fetched(body, conn):
    # turns a DocumentFetched message into the DocumentExtracted event to publish; anything
    # that is not an Unreadable error (database down, ...) is left to the caller to retry
    message = parse(body)
    payload = message["payload"]
    context = f"doc_id={payload['doc_id']} correlationId={message['correlationId']}"

    pdf = read_pdf(payload["path"], context)
    try:
        pages, page_count = extract_pages(pdf)
    except Exception as e:
        raise Unreadable(f"cannot extract text: {e!r} ({context})")
    if not pages:
        raise Unreadable(f"the PDF has no text ({context})")

    doc = {
        "doc_id": payload["doc_id"],
        "title": payload["title"],
        "url": payload["url"],
        "page_count": page_count,
        "pages": pages,
    }
    store.save_document(doc, conn)
    logger.info("extracted %d of %d pages (%s)", len(pages), page_count, context)

    return {
        "eventType": "DocumentExtracted",
        "eventId": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "correlationId": message["correlationId"],
        "payload": doc,
    }


def parse(body):
    try:
        message = json.loads(body)
        payload = message["payload"]
        if message["eventType"] != "DocumentFetched" or not message["correlationId"]:
            raise ValueError("not a DocumentFetched event")
        for key in REQUIRED:
            if not isinstance(payload[key], str) or not payload[key]:
                raise ValueError(f"payload.{key} is missing")
    except (ValueError, KeyError, TypeError) as e:
        raise Unreadable(f"bad message: {e!r}")
    return message


def read_pdf(path, context):
    pdf_path = Path(path).resolve()
    # the path comes from a message, so only files in the shared volume are read
    if not pdf_path.is_relative_to(PDF_DIR.resolve()):
        raise Unreadable(f"path is outside {PDF_DIR} ({context})")
    try:
        return pdf_path.read_bytes()
    except OSError as e:
        raise Unreadable(f"cannot read the PDF: {e!r} ({context})")
