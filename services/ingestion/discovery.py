import json
import logging
import os
import time
from datetime import datetime, timezone
from urllib.parse import unquote, urljoin, urlparse

import httpx
import pika
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

EXCHANGE = "rag.topic"
ROUTING_KEY = "document.discovered"

CRAWL_DELAY = 5  # seconds, "Crawl-delay: 5" in lancaster.ac.uk/robots.txt
last_request = None


def get_pdf_links(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        url = urljoin(base_url, a["href"]).split("#")[0]
        path = urlparse(url).path
        if not path.lower().endswith(".pdf") or url in seen:
            continue
        seen.add(url)
        title = " ".join(a.get_text().split()) or unquote(path.rsplit("/", 1)[-1])
        links.append({"url": url, "title": title})
    return links


def publish(docs, rabbitmq_url):
    connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
    try:
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
        for doc in docs:
            event = {
                "event": "DocumentDiscovered",
                "url": doc["url"],
                "title": doc["title"],
                "discovered_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            channel.basic_publish(
                exchange=EXCHANGE,
                routing_key=ROUTING_KEY,
                body=json.dumps(event),
                properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
            )
    finally:
        connection.close()


def discover():
    marp_url = os.environ["MARP_URL"]
    headers = {"User-Agent": os.environ["USER_AGENT"]}

    global last_request
    if last_request is not None:
        wait = CRAWL_DELAY - (time.monotonic() - last_request)
        if wait > 0:
            time.sleep(wait)

    try:
        with httpx.Client(headers=headers, follow_redirects=True, timeout=30) as client:
            resp = client.get(marp_url)
    finally:
        last_request = time.monotonic()
    resp.raise_for_status()

    docs = get_pdf_links(resp.text, marp_url)
    publish(docs, os.environ["RABBITMQ_URL"])
    logger.info("published %d DocumentDiscovered events", len(docs))
    return len(docs)
