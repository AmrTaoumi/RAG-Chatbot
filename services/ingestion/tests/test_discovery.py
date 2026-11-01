import json
import uuid
from unittest.mock import MagicMock

import httpx
import pika
import psycopg
import pytest

import discovery

BASE = "https://www.lancaster.ac.uk/marp/"

HTML = """
<a href="/media/Academic-Integrity-Regs.pdf">Academic   Integrity
   Regulations</a>
<a href="/media/Academic-Integrity-Regs.pdf">duplicate</a>
<a href="https://other.example/Absolute.PDF?download=1#page=2">Absolute</a>
<a href="/media/No%20Title.pdf"><img src="x.png"></a>
<a href="/about/">Not a PDF</a>
"""


def test_get_pdf_links():
    assert discovery.get_pdf_links(HTML, BASE) == [
        {
            "url": "https://www.lancaster.ac.uk/media/Academic-Integrity-Regs.pdf",
            "title": "Academic Integrity Regulations",
        },
        {"url": "https://other.example/Absolute.PDF?download=1", "title": "Absolute"},
        {"url": "https://www.lancaster.ac.uk/media/No%20Title.pdf", "title": "No Title.pdf"},
    ]


def test_publish(monkeypatch):
    connection = MagicMock()
    channel = connection.channel.return_value
    monkeypatch.setattr(pika, "BlockingConnection", lambda params: connection)

    discovery.publish([{"url": "https://x.example/a.pdf", "title": "A"}], "amqp://guest:guest@localhost/")

    channel.exchange_declare.assert_called_once_with(
        exchange="rag.topic", exchange_type="topic", durable=True
    )
    channel.queue_declare.assert_called_once_with(queue="ingestion.fetch", durable=True)
    channel.queue_bind.assert_called_once_with(
        queue="ingestion.fetch", exchange="rag.topic", routing_key="document.discovered"
    )
    call = channel.basic_publish.call_args.kwargs
    channel.confirm_delivery.assert_called_once()
    assert call["mandatory"] is True
    assert call["routing_key"] == "document.discovered"
    assert call["properties"].delivery_mode == 2
    assert call["properties"].content_type == "application/json"

    event = json.loads(call["body"])
    assert event["eventType"] == "DocumentDiscovered"
    assert event["payload"] == {"url": "https://x.example/a.pdf", "title": "A"}
    assert event["timestamp"].endswith("Z")
    uuid.UUID(event["eventId"])
    uuid.UUID(event["correlationId"])
    connection.close.assert_called_once()


def test_publish_gives_each_document_its_own_ids(monkeypatch):
    connection = MagicMock()
    channel = connection.channel.return_value
    monkeypatch.setattr(pika, "BlockingConnection", lambda params: connection)
    docs = [{"url": f"https://x.example/{n}.pdf", "title": n} for n in "ab"]

    discovery.publish(docs, "amqp://x")

    events = [json.loads(c.kwargs["body"]) for c in channel.basic_publish.call_args_list]
    assert len({e["eventId"] for e in events}) == 2
    assert len({e["correlationId"] for e in events}) == 2


def test_publish_reports_each_event_as_it_is_confirmed(monkeypatch):
    connection = MagicMock()
    channel = connection.channel.return_value
    channel.basic_publish.side_effect = [None, pika.exceptions.UnroutableError([])]
    monkeypatch.setattr(pika, "BlockingConnection", lambda params: connection)
    sent = []
    docs = [{"url": f"https://x.example/{n}.pdf", "title": n} for n in "ab"]

    with pytest.raises(pika.exceptions.UnroutableError):
        discovery.publish(docs, "amqp://x", on_published=sent.append)

    assert sent == [docs[0]]


connect_kwargs = {}


def _setup(monkeypatch, robots=(200, "User-agent: *\nAllow: /"), seen=(), lock=True):
    published, marked = [], []
    real_client = httpx.Client

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(robots[0], text=robots[1])
        return httpx.Response(200, text=HTML)

    transport = httpx.MockTransport(handler)
    monkeypatch.setenv("MARP_URL", BASE)
    monkeypatch.setenv("USER_AGENT", "test")
    monkeypatch.setenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setattr(httpx, "Client", lambda **kw: real_client(transport=transport, **kw))

    def fake_publish(docs, url, on_published=None):
        for doc in docs:
            published.append(doc)
            on_published(doc)

    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.execute.return_value.fetchone.return_value = (lock,)
    connect_kwargs.clear()
    monkeypatch.setattr(psycopg, "connect", lambda *a, **kw: connect_kwargs.update(kw) or conn)
    monkeypatch.setattr(discovery, "publish", fake_publish)
    monkeypatch.setattr(
        discovery, "filter_new", lambda docs, conn: [d for d in docs if d["url"] not in seen]
    )
    monkeypatch.setattr(discovery, "mark_discovered", lambda doc, conn: marked.append(doc))
    monkeypatch.setattr(discovery, "last_request", None)
    monkeypatch.setattr(discovery.time, "sleep", lambda s: None)
    return published, marked


def test_discover(monkeypatch):
    published, marked = _setup(monkeypatch)
    assert discovery.discover() == 3
    assert len(published) == 3
    assert marked == published
    assert connect_kwargs["connect_timeout"] == 10


def test_discover_skips_already_seen(monkeypatch):
    seen = {"https://www.lancaster.ac.uk/media/Academic-Integrity-Regs.pdf"}
    published, marked = _setup(monkeypatch, seen=seen)
    assert discovery.discover() == 2
    assert all(d["url"] not in seen for d in published)


def test_discover_second_run_publishes_nothing(monkeypatch):
    seen = {d["url"] for d in discovery.get_pdf_links(HTML, BASE)}
    published, _ = _setup(monkeypatch, seen=seen)
    assert discovery.discover() == 0
    assert published == []


def test_discover_refuses_when_another_run_holds_the_lock(monkeypatch):
    published, _ = _setup(monkeypatch, lock=False)
    requests = []
    monkeypatch.setattr(discovery, "polite_get", lambda *a: requests.append(a))
    with pytest.raises(discovery.DiscoveryBusy):
        discovery.discover()
    assert published == []
    assert requests == []


def test_discover_respects_robots_disallow(monkeypatch):
    published, _ = _setup(monkeypatch, robots=(200, "User-agent: *\nDisallow: /marp/"))
    with pytest.raises(discovery.RobotsDisallowed):
        discovery.discover()
    assert published == []


def test_discover_robots_forbidden_blocks(monkeypatch):
    _setup(monkeypatch, robots=(403, ""))
    with pytest.raises(discovery.RobotsDisallowed):
        discovery.discover()


def test_discover_robots_missing_allows(monkeypatch):
    _setup(monkeypatch, robots=(404, ""))
    assert discovery.discover() == 3


def test_discover_uses_robots_crawl_delay(monkeypatch):
    sleeps = []
    _setup(monkeypatch, robots=(200, "User-agent: *\nCrawl-delay: 9"))
    monkeypatch.setattr(discovery.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(discovery.time, "sleep", sleeps.append)
    discovery.discover()
    assert sleeps == [9]


def test_discover_waits_between_runs(monkeypatch):
    sleeps = []
    _setup(monkeypatch)
    monkeypatch.setattr(discovery, "last_request", 100.0)
    monkeypatch.setattr(discovery.time, "monotonic", lambda: 102.0)
    monkeypatch.setattr(discovery.time, "sleep", sleeps.append)

    discovery.discover()
    assert sleeps[0] == 3.0
