import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import discovery

logger = logging.getLogger(__name__)

PDF_DIR = Path(os.environ.get("PDF_DIR", "/data/pdfs"))
REQUIRED = ("url", "title")
RETRY_STATUSES = {408, 429}  # a 4xx that may pass meaning every other 4xx is final

# robots.txt per site
robots_cache = {}


class Unreadable(Exception):
    pass


def handle_discovered(body, client, user_agent):
    # turns a DocumentDiscovered message into the DocumentFetched event to publish; a network
    # error or a 5xx from the site is not an Unreadable error, so the caller retries it
    message = parse(body)
    payload = message["payload"]
    doc_id = hashlib.md5(payload["url"].encode()).hexdigest()
    context = f"doc_id={doc_id} correlationId={message['correlationId']}"

    path = PDF_DIR / f"{doc_id}.pdf"
    if path.is_file():
        logger.info("already downloaded, publishing again (%s)", context)
    else:
        pdf = download(client, payload["url"], user_agent, context)
        partial = path.with_suffix(".part")
        partial.write_bytes(pdf)
        os.replace(partial, path)
        logger.info("downloaded %d bytes (%s)", len(pdf), context)

    return {
        "eventType": "DocumentFetched",
        "eventId": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "correlationId": message["correlationId"],
        "payload": {
            "doc_id": doc_id,
            "url": payload["url"],
            "title": payload["title"],
            "path": str(path),
        },
    }


def parse(body):
    try:
        message = json.loads(body)
        payload = message["payload"]
        if message["eventType"] != "DocumentDiscovered" or not message["correlationId"]:
            raise ValueError("not a DocumentDiscovered event")
        for key in REQUIRED:
            if not isinstance(payload[key], str) or not payload[key]:
                raise ValueError(f"payload.{key} is missing")
        if urlparse(payload["url"]).scheme not in ("http", "https"):
            raise ValueError("payload.url is not an http(s) link")
    except (ValueError, KeyError, TypeError) as e:
        raise Unreadable(f"bad message: {e!r}")
    return message


def robots_for(client, url):
    parts = urlparse(url)
    site = f"{parts.scheme}://{parts.netloc}"
    if site not in robots_cache:
        robots_cache[site] = discovery.load_robots(client, url)
    return robots_cache[site]


def download(client, url, user_agent, context):
    robots = robots_for(client, url)
    if not robots.can_fetch(user_agent, url):
        raise Unreadable(f"robots.txt disallows {url} ({context})")
    delay = robots.crawl_delay(user_agent) or discovery.CRAWL_DELAY
    resp = discovery.polite_get(client, url, delay)
    if resp.status_code in RETRY_STATUSES or resp.status_code >= 500:
        resp.raise_for_status()
    if resp.status_code >= 400:
        raise Unreadable(f"{url} answered {resp.status_code} ({context})")
    if not resp.content.startswith(b"%PDF-"):
        raise Unreadable(f"{url} is not a PDF ({context})")
    return resp.content
