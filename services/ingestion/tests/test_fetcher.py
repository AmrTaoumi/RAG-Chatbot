import hashlib
import json
import uuid

import httpx
import pytest

import discovery
import fetcher

URL = "https://www.lancaster.ac.uk/media/Academic-Integrity-Regs.pdf"
DOC_ID = hashlib.md5(URL.encode()).hexdigest()
CORRELATION_ID = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
UA = "TestBot/1.0"
PDF = b"%PDF-1.4 pretend pdf"
ROBOTS = "User-agent: *\nDisallow: /private/\n"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(fetcher, "PDF_DIR", tmp_path)
    monkeypatch.setattr(fetcher, "robots_cache", {})
    monkeypatch.setattr(discovery, "polite_get", lambda client, url, delay: client.get(url))


def site(pdf_status=200, pdf_body=PDF, robots_status=200, robots=ROBOTS):
    requests = []

    def respond(request):
        requests.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(robots_status, text=robots)
        return httpx.Response(pdf_status, content=pdf_body)

    return httpx.Client(transport=httpx.MockTransport(respond)), requests


def discovered(url=URL, **payload):
    return json.dumps(
        {
            "eventType": "DocumentDiscovered",
            "eventId": "3f2b8c1e-5d0a-4c1e-9a7b-1e2d3c4b5a61",
            "timestamp": "2026-10-20T12:00:00Z",
            "correlationId": CORRELATION_ID,
            "payload": {"url": url, "title": "Academic Integrity Regulations", **payload},
        }
    )


def test_downloads_the_pdf_and_builds_the_document_fetched_event(tmp_path):
    client, _ = site()

    event = fetcher.handle_discovered(discovered(), client, UA)

    assert (tmp_path / f"{DOC_ID}.pdf").read_bytes() == PDF
    assert event["eventType"] == "DocumentFetched"
    assert event["correlationId"] == CORRELATION_ID
    assert event["timestamp"].endswith("Z")
    assert uuid.UUID(event["eventId"]) != uuid.UUID("3f2b8c1e-5d0a-4c1e-9a7b-1e2d3c4b5a61")
    assert event["payload"] == {
        "doc_id": DOC_ID,
        "url": URL,
        "title": "Academic Integrity Regulations",
        "path": str(tmp_path / f"{DOC_ID}.pdf"),
    }


def test_leaves_no_partial_file_behind(tmp_path):
    client, _ = site()
    fetcher.handle_discovered(discovered(), client, UA)
    assert [p.name for p in tmp_path.iterdir()] == [f"{DOC_ID}.pdf"]


def test_a_file_already_on_the_volume_is_not_downloaded_again(tmp_path):
    (tmp_path / f"{DOC_ID}.pdf").write_bytes(b"%PDF-1.4 earlier")
    client, requests = site()

    event = fetcher.handle_discovered(discovered(), client, UA)

    assert requests == []
    assert event["payload"]["doc_id"] == DOC_ID
    assert (tmp_path / f"{DOC_ID}.pdf").read_bytes() == b"%PDF-1.4 earlier"


def test_robots_txt_is_fetched_once_per_site():
    client, requests = site()
    fetcher.handle_discovered(discovered(), client, UA)
    fetcher.handle_discovered(discovered(url=URL.replace("Regs", "Other")), client, UA)
    assert requests.count("https://www.lancaster.ac.uk/robots.txt") == 1


def test_uses_the_crawl_delay_from_robots_txt(monkeypatch):
    delays = []
    monkeypatch.setattr(
        discovery, "polite_get", lambda client, url, delay: delays.append(delay) or client.get(url)
    )
    client, _ = site(robots="User-agent: *\nCrawl-delay: 9\n")
    fetcher.handle_discovered(discovered(), client, UA)
    assert delays[-1] == 9


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        json.dumps({"eventType": "DocumentDiscovered"}),
        json.dumps({"eventType": "DocumentFetched", "correlationId": "c", "payload": {}}),
        discovered(url=""),
        discovered(title=None),
        discovered(url="ftp://x.example/a.pdf"),
        discovered(url="file:///etc/passwd"),
    ],
)
def test_bad_messages_are_unreadable(tmp_path, body):
    client, requests = site()
    with pytest.raises(fetcher.Unreadable):
        fetcher.handle_discovered(body, client, UA)
    assert requests == []
    assert list(tmp_path.iterdir()) == []


def test_robots_txt_disallowing_the_url_is_unreadable(tmp_path):
    client, _ = site(robots="User-agent: *\nDisallow: /media/\n")
    with pytest.raises(fetcher.Unreadable, match="robots.txt disallows"):
        fetcher.handle_discovered(discovered(), client, UA)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("status", [403, 404, 410])
def test_a_final_4xx_is_unreadable(tmp_path, status):
    client, _ = site(pdf_status=status)
    with pytest.raises(fetcher.Unreadable, match=str(status)):
        fetcher.handle_discovered(discovered(), client, UA)
    assert list(tmp_path.iterdir()) == []


def test_a_page_that_is_not_a_pdf_is_unreadable(tmp_path):
    client, _ = site(pdf_body=b"<html>Sorry, not found</html>")
    with pytest.raises(fetcher.Unreadable, match="not a PDF"):
        fetcher.handle_discovered(discovered(), client, UA)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("status", [408, 429, 500, 503])
def test_a_temporary_failure_is_not_unreadable(tmp_path, status):
    client, _ = site(pdf_status=status)
    with pytest.raises(httpx.HTTPStatusError):
        fetcher.handle_discovered(discovered(), client, UA)
    assert list(tmp_path.iterdir()) == []


def test_a_network_error_is_not_unreadable():
    def refuse(request):
        raise httpx.ConnectError("refused")

    client = httpx.Client(transport=httpx.MockTransport(refuse))
    with pytest.raises(httpx.ConnectError):
        fetcher.handle_discovered(discovered(), client, UA)


def test_the_error_names_the_document_and_correlation_id():
    client, _ = site(pdf_status=404)
    with pytest.raises(fetcher.Unreadable) as error:
        fetcher.handle_discovered(discovered(), client, UA)
    assert f"doc_id={DOC_ID} correlationId={CORRELATION_ID}" in str(error.value)
