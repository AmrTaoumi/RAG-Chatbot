import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

CHAT_ORIGIN = "http://localhost:8004"
OTHER_ORIGIN = "http://evil.example"


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_parse_origins_splits_and_strips():
    raw = " http://localhost:8004 , http://127.0.0.1:8004/ ,,"
    assert main.parse_origins(raw) == ["http://localhost:8004", "http://127.0.0.1:8004"]


@pytest.mark.parametrize("raw", ["*", "http://localhost:8004,*", " * "])
def test_parse_origins_rejects_wildcard(raw):
    with pytest.raises(RuntimeError, match=r"\*"):
        main.parse_origins(raw)


@pytest.mark.parametrize("raw", [None, "", " , "])
def test_parse_origins_rejects_empty(raw):
    with pytest.raises(RuntimeError, match="not set"):
        main.parse_origins(raw)


@pytest.mark.parametrize("origin", ["http://localhost:8004", "http://127.0.0.1:8004"])
def test_allowed_origin_gets_cors_headers(origin):
    r = client.get("/health", headers={"Origin": origin})
    assert r.headers["access-control-allow-origin"] == origin
    assert r.headers["access-control-allow-credentials"] == "true"


def test_unlisted_origin_gets_no_allow_origin():
    r = client.get("/health", headers={"Origin": OTHER_ORIGIN})
    assert "access-control-allow-origin" not in r.headers


def test_preflight_from_chat_origin_succeeds():
    r = client.options(
        "/auth/login",
        headers={
            "Origin": CHAT_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == CHAT_ORIGIN
    assert r.headers["access-control-allow-credentials"] == "true"
    allowed = r.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed
    assert "content-type" in allowed


def test_preflight_from_unlisted_origin_rejected():
    r = client.options(
        "/auth/login",
        headers={"Origin": OTHER_ORIGIN, "Access-Control-Request-Method": "POST"},
    )
    assert r.status_code == 400
    assert "access-control-allow-origin" not in r.headers
