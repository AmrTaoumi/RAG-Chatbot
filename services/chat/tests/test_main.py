import httpx
import pytest
from fastapi.testclient import TestClient

import main
from prompt import FALLBACK_ANSWER
from tests.fake_snippets import FAKE_SNIPPETS

client = TestClient(main.app)


@pytest.fixture
def published(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "publish_answer_generated", lambda *a: calls.append(a))
    return calls


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_chat_returns_answer_and_citations(monkeypatch, published):
    monkeypatch.setattr(main, "search", lambda q, cid: FAKE_SNIPPETS)
    monkeypatch.setattr(main, "ask", lambda messages: "Zero marks [1][7].")
    r = client.post("/chat", json={"question": "What if I miss an exam?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "Zero marks [1]."
    assert body["citations"] == [
        {"title": FAKE_SNIPPETS[0]["title"], "url": FAKE_SNIPPETS[0]["url"], "page": FAKE_SNIPPETS[0]["page"]}
    ]
    assert len(published) == 1


def test_no_snippets_gives_fallback_without_calling_llm(monkeypatch, published):
    monkeypatch.setattr(main, "search", lambda q, cid: [])

    def fail(messages):
        raise AssertionError("LLM should not be called")

    monkeypatch.setattr(main, "ask", fail)
    r = client.post("/chat", json={"question": "anything"})
    assert r.json() == {"answer": FALLBACK_ANSWER, "citations": []}


def test_retrieval_down_returns_503(monkeypatch, published):
    def down(q, cid):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(main, "search", down)
    r = client.post("/chat", json={"question": "anything"})
    assert r.status_code == 503
    assert published == []


def test_llm_error_returns_502(monkeypatch, published):
    monkeypatch.setattr(main, "search", lambda q, cid: FAKE_SNIPPETS)

    def broken(messages):
        raise RuntimeError("OpenRouter error 500")

    monkeypatch.setattr(main, "ask", broken)
    r = client.post("/chat", json={"question": "anything"})
    assert r.status_code == 502


def test_empty_question_rejected():
    assert client.post("/chat", json={"question": ""}).status_code == 422

def test_low_score_gives_fallback_without_calling_llm(monkeypatch, published):
    low = [dict(FAKE_SNIPPETS[0], score=main.SCORE_THRESHOLD - 0.1)]
    monkeypatch.setattr(main, "search", lambda q, cid: low)

    def fail(messages):
        raise AssertionError("LLM should not be called")

    monkeypatch.setattr(main, "ask", fail)
    r = client.post("/chat", json={"question": "where is the library?"})
    assert r.json() == {"answer": FALLBACK_ANSWER, "citations": []}
    assert len(published) == 1


def test_score_at_threshold_calls_llm(monkeypatch, published):
    exact = [dict(FAKE_SNIPPETS[0], score=main.SCORE_THRESHOLD)]
    monkeypatch.setattr(main, "search", lambda q, cid: exact)
    monkeypatch.setattr(main, "ask", lambda messages: "Zero marks [1].")
    r = client.post("/chat", json={"question": "late penalty?"})
    assert r.json()["citations"] != []