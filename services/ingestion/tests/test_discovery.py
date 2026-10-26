import json
from unittest.mock import MagicMock

import httpx
import pika

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
    call = channel.basic_publish.call_args.kwargs
    assert call["routing_key"] == "document.discovered"
    assert call["properties"].delivery_mode == 2
    assert call["properties"].content_type == "application/json"

    event = json.loads(call["body"])
    assert event["event"] == "DocumentDiscovered"
    assert event["url"] == "https://x.example/a.pdf"
    assert event["title"] == "A"
    assert event["discovered_at"].endswith("Z")
    connection.close.assert_called_once()


def test_discover(monkeypatch):
    published = []
    real_client = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=HTML))

    monkeypatch.setenv("MARP_URL", BASE)
    monkeypatch.setenv("USER_AGENT", "test")
    monkeypatch.setenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
    monkeypatch.setattr(httpx, "Client", lambda **kw: real_client(transport=transport, **kw))
    monkeypatch.setattr(discovery, "publish", lambda docs, url: published.extend(docs))
    monkeypatch.setattr(discovery, "last_request", None)

    assert discovery.discover() == 3
    assert len(published) == 3


def test_discover_waits_between_runs(monkeypatch):
    sleeps = []
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=HTML))
    real_client = httpx.Client

    monkeypatch.setenv("MARP_URL", BASE)
    monkeypatch.setenv("USER_AGENT", "test")
    monkeypatch.setenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
    monkeypatch.setattr(httpx, "Client", lambda **kw: real_client(transport=transport, **kw))
    monkeypatch.setattr(discovery, "publish", lambda docs, url: None)
    monkeypatch.setattr(discovery, "last_request", 100.0)
    monkeypatch.setattr(discovery.time, "monotonic", lambda: 102.0)
    monkeypatch.setattr(discovery.time, "sleep", sleeps.append)

    discovery.discover()
    assert sleeps == [3.0]
