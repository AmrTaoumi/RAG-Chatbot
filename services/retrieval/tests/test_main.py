import json
import uuid
from unittest.mock import MagicMock

import psycopg
import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

ROW = ("d-p3-c0", "d", "Title", "http://u", 3, "text", 0.912345)


def fake_conn(rows):
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.execute.return_value.fetchall.return_value = rows
    return conn


@pytest.fixture
def published(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "publish_retrieval_completed", lambda *a: calls.append(a))
    return calls


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_search_returns_contract_shape(monkeypatch, published):
    monkeypatch.setattr(main.psycopg, "connect", lambda *a, **kw: fake_conn([ROW]))
    r = client.get("/search", params={"q": "late"})
    assert r.status_code == 200
    assert r.json() == {
        "query": "late",
        "results": [
            {"chunk_id": "d-p3-c0", "doc_id": "d", "title": "Title", "url": "http://u",
             "page": 3, "text": "text", "score": 0.9123}
        ],
    }


def test_search_uses_cosine_operator_and_k(monkeypatch, published):
    conn = fake_conn([])
    monkeypatch.setattr(main.psycopg, "connect", lambda *a, **kw: conn)
    client.get("/search", params={"q": "x", "k": 7})
    sql, params = conn.execute.call_args.args
    assert "<=>" in sql and "ORDER BY" in sql and "chunk_id" in sql
    assert params["k"] == 7


@pytest.mark.parametrize("params", [{}, {"q": ""}, {"q": "x", "k": 0}, {"q": "x", "k": 21}])
def test_search_rejects_bad_params(params):
    assert client.get("/search", params=params).status_code == 422


def test_correlation_id_passed_through(monkeypatch, published):
    monkeypatch.setattr(main.psycopg, "connect", lambda *a, **kw: fake_conn([]))
    client.get("/search", params={"q": "x"}, headers={"X-Correlation-ID": "abc"})
    assert published[0][3] == "abc"


def test_correlation_id_created_when_missing(monkeypatch, published):
    monkeypatch.setattr(main.psycopg, "connect", lambda *a, **kw: fake_conn([]))
    client.get("/search", params={"q": "x"})
    uuid.UUID(published[0][3])


def test_database_down_returns_503(monkeypatch, published):
    def boom(*a, **kw):
        raise psycopg.OperationalError("down")

    monkeypatch.setattr(main.psycopg, "connect", boom)
    r = client.get("/search", params={"q": "x"})
    assert r.status_code == 503
    assert r.json() == {"detail": "database unavailable"}
    assert published == []


def test_event_envelope(monkeypatch):
    channel = MagicMock()
    conn = MagicMock()
    conn.channel.return_value = channel
    monkeypatch.setattr(main.pika, "BlockingConnection", lambda *a, **kw: conn)
    results = [{"chunk_id": "c", "doc_id": "d", "title": "T", "url": "u", "page": 1,
                "text": "secret", "score": 0.5}]

    main.publish_retrieval_completed("q", 5, results, "cid")

    kw = channel.basic_publish.call_args.kwargs
    assert kw["exchange"] == "rag.topic" and kw["routing_key"] == "retrieval.completed"
    assert kw["properties"].delivery_mode == 2
    assert kw["properties"].content_type == "application/json"
    event = json.loads(kw["body"])
    assert event["eventType"] == "RetrievalCompleted"
    assert event["correlationId"] == "cid"
    uuid.UUID(event["eventId"])
    assert event["payload"]["query"] == "q" and event["payload"]["k"] == 5
    assert "text" not in event["payload"]["results"][0]
    conn.close.assert_called_once()


def test_broker_failure_does_not_fail_search(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("broker down")

    monkeypatch.setattr(main.pika, "BlockingConnection", boom)
    monkeypatch.setattr(main.psycopg, "connect", lambda *a, **kw: fake_conn([ROW]))
    assert client.get("/search", params={"q": "x"}).status_code == 200
