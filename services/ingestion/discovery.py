import json
import logging
import os
import time
import urllib.robotparser
from datetime import datetime, timezone
from urllib.parse import unquote, urljoin, urlparse

import httpx
import pika
import psycopg
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

EXCHANGE = "rag.topic"
ROUTING_KEY = "document.discovered"

CRAWL_DELAY = 5  # seconds, "Crawl-delay: 5" in lancaster.ac.uk/robots.txt
last_request = None

LOCK_ID = 7_001  # arbitrary key for the Postgres advisory lock


class RobotsDisallowed(Exception):
    pass


class DiscoveryBusy(Exception):
    pass


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


def publish(docs, rabbitmq_url, on_published=None):
    connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
    try:
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
        # with confirms + mandatory, an unroutable message raises instead of vanishing
        channel.confirm_delivery()
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
                mandatory=True,
                body=json.dumps(event),
                properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
            )
            if on_published:
                on_published(doc)
    finally:
        connection.close()


def polite_get(client, url, delay):
    global last_request
    if last_request is not None:
        wait = delay - (time.monotonic() - last_request)
        if wait > 0:
            time.sleep(wait)
    try:
        return client.get(url)
    finally:
        last_request = time.monotonic()


def load_robots(client, url):
    resp = polite_get(client, urljoin(url, "/robots.txt"), CRAWL_DELAY)
    robots = urllib.robotparser.RobotFileParser()
    if resp.status_code in (401, 403):
        robots.disallow_all = True  # access denied counts as a "no"
    elif resp.status_code >= 500:
        resp.raise_for_status()  # can't tell what's allowed, so don't crawl
    elif resp.status_code >= 400:
        robots.allow_all = True  # no robots.txt means no restrictions
    else:
        robots.parse(resp.text.splitlines())
    return robots


def filter_new(docs, conn):
    if not docs:
        return []
    conn.execute("CREATE TABLE IF NOT EXISTS discovered_documents (url TEXT PRIMARY KEY)")
    rows = conn.execute(
        "SELECT url FROM discovered_documents WHERE url = ANY(%s)",
        ([d["url"] for d in docs],),
    ).fetchall()
    seen = {row[0] for row in rows}
    return [d for d in docs if d["url"] not in seen]


def mark_discovered(doc, conn):
    conn.execute(
        "INSERT INTO discovered_documents (url) VALUES (%s) ON CONFLICT DO NOTHING",
        (doc["url"],),
    )


def discover():
    marp_url = os.environ["MARP_URL"]
    user_agent = os.environ["USER_AGENT"]

    # autocommit so each URL is saved as soon as its event is confirmed; if
    # publishing dies halfway, the next run only redoes the unsent ones
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, connect_timeout=10) as conn:
        # take the lock before touching the site, so overlapping runs don't both
        # crawl it; it belongs to this connection and is released when it closes
        if not conn.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_ID,)).fetchone()[0]:
            raise DiscoveryBusy("another discovery run is in progress")

        with httpx.Client(headers={"User-Agent": user_agent}, follow_redirects=True, timeout=30) as client:
            robots = load_robots(client, marp_url)
            if not robots.can_fetch(user_agent, marp_url):
                raise RobotsDisallowed(f"robots.txt disallows {marp_url}")
            delay = robots.crawl_delay(user_agent) or CRAWL_DELAY
            resp = polite_get(client, marp_url, delay)
        resp.raise_for_status()

        docs = filter_new(get_pdf_links(resp.text, marp_url), conn)
        publish(docs, os.environ["RABBITMQ_URL"], on_published=lambda doc: mark_discovered(doc, conn))
    logger.info("published %d new DocumentDiscovered events", len(docs))
    return len(docs)
