import pytest
from fastapi.testclient import TestClient

import discovery
from main import app

client = TestClient(app)


def test_discover(monkeypatch):
    monkeypatch.setattr(discovery, "discover", lambda: 3)
    r = client.post("/discover")
    assert r.status_code == 200
    assert r.json() == {"published": 3}


@pytest.mark.parametrize(
    "error, status",
    [(discovery.RobotsDisallowed("no"), 403), (discovery.DiscoveryBusy("busy"), 409)],
)
def test_discover_errors(monkeypatch, error, status):
    def fail():
        raise error

    monkeypatch.setattr(discovery, "discover", fail)
    assert client.post("/discover").status_code == status


def test_openapi_docs():
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/health", "/discover"} <= set(paths)
    assert {"200", "403", "409"} <= set(paths["/discover"]["post"]["responses"])
