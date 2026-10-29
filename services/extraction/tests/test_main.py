from unittest.mock import MagicMock

import psycopg
import store
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

DOC = {
    "doc_id": "9e107d9d372bb6826bd81d3542a419d6",
    "title": "Academic Integrity Regulations",
    "url": "https://x.example/a.pdf",
    "page_count": 12,
    "extracted_at": "2026-10-20T12:01:00Z",
}


def fake_connection(monkeypatch):
    conn = MagicMock()
    conn.__enter__.return_value = conn
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setattr(psycopg, "connect", lambda *a, **kw: conn)
    return conn


def test_documents(monkeypatch):
    conn = fake_connection(monkeypatch)
    monkeypatch.setattr(store, "list_documents", lambda c: [DOC] if c is conn else [])
    r = client.get("/documents")
    assert r.status_code == 200
    assert r.json() == [DOC]


def test_documents_returns_503_when_the_database_is_down(monkeypatch):
    def refuse(*args, **kwargs):
        raise psycopg.OperationalError("connection refused")

    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setattr(psycopg, "connect", refuse)
    r = client.get("/documents")
    assert r.status_code == 503
    assert r.json() == {"detail": "database unavailable"}


def test_documents_creates_the_table_first(monkeypatch):
    conn = fake_connection(monkeypatch)
    calls = []
    monkeypatch.setattr(store, "ensure_table", lambda c: calls.append("ensure_table"))
    monkeypatch.setattr(store, "list_documents", lambda c: calls.append("list_documents") or [])
    assert client.get("/documents").json() == []
    assert calls == ["ensure_table", "list_documents"]
