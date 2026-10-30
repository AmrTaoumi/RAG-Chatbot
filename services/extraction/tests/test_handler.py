import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import psycopg
import pytest

import handler
import store

SAMPLE = Path(__file__).parent / "fixtures" / "sample.pdf"
DOC_ID = "9e107d9d372bb6826bd81d3542a419d6"
CORRELATION_ID = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


@pytest.fixture
def volume(tmp_path, monkeypatch):
    (tmp_path / f"{DOC_ID}.pdf").write_bytes(SAMPLE.read_bytes())
    monkeypatch.setattr(handler, "PDF_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def saved(monkeypatch):
    saved = []
    monkeypatch.setattr(store, "save_document", lambda doc, conn: saved.append(doc))
    return saved


def fetched(volume=None, **payload):
    fields = {
        "doc_id": DOC_ID,
        "url": "https://x.example/a.pdf",
        "title": "Academic Integrity Regulations",
        "path": f"{volume}/{DOC_ID}.pdf" if volume else "/x",
    }
    return json.dumps(
        {
            "eventType": "DocumentFetched",
            "eventId": "3f2b8c1e-5d0a-4c1e-9a7b-1e2d3c4b5a62",
            "timestamp": "2026-10-20T12:00:30Z",
            "correlationId": CORRELATION_ID,
            "payload": {**fields, **payload},
        }
    )


def test_handle_fetched_builds_the_document_extracted_event(volume, saved):
    event = handler.handle_fetched(fetched(volume), MagicMock())

    assert event["eventType"] == "DocumentExtracted"
    assert event["correlationId"] == CORRELATION_ID
    assert event["timestamp"].endswith("Z")
    assert uuid.UUID(event["eventId"]) != uuid.UUID("3f2b8c1e-5d0a-4c1e-9a7b-1e2d3c4b5a62")
    assert event["payload"] == {
        "doc_id": DOC_ID,
        "url": "https://x.example/a.pdf",
        "title": "Academic Integrity Regulations",
        "page_count": 2,
        "pages": [{"page": 1, "text": "Page one text"}, {"page": 2, "text": "Page two text"}],
    }


def test_handle_fetched_saves_the_document(volume, saved):
    event = handler.handle_fetched(fetched(volume), MagicMock())
    assert saved == [event["payload"]]


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        json.dumps({"eventType": "DocumentFetched"}),
        json.dumps({"eventType": "DocumentExtracted", "correlationId": "c", "payload": {}}),
        fetched(doc_id=""),
        fetched(title=None),
    ],
)
def test_bad_messages_are_unreadable(volume, saved, body):
    with pytest.raises(handler.Unreadable):
        handler.handle_fetched(body, MagicMock())
    assert saved == []


def test_missing_file_is_unreadable(volume, saved):
    with pytest.raises(handler.Unreadable, match="cannot read the PDF"):
        handler.handle_fetched(fetched(volume, path=f"{volume}/missing.pdf"), MagicMock())
    assert saved == []


def test_path_outside_the_volume_is_unreadable(volume, saved, tmp_path_factory):
    elsewhere = tmp_path_factory.mktemp("elsewhere") / "a.pdf"
    elsewhere.write_bytes(SAMPLE.read_bytes())
    with pytest.raises(handler.Unreadable, match="outside"):
        handler.handle_fetched(fetched(volume, path=str(elsewhere)), MagicMock())
    with pytest.raises(handler.Unreadable, match="outside"):
        handler.handle_fetched(fetched(volume, path=f"{volume}/../../etc/passwd"), MagicMock())
    assert saved == []


def test_a_file_that_is_not_a_pdf_is_unreadable(volume, saved):
    (volume / f"{DOC_ID}.pdf").write_bytes(b"<html>404 not found</html>")
    with pytest.raises(handler.Unreadable, match="cannot extract text"):
        handler.handle_fetched(fetched(volume), MagicMock())
    assert saved == []


def test_a_pdf_without_text_is_unreadable(volume, saved, monkeypatch):
    monkeypatch.setattr(handler, "extract_pages", lambda pdf: ([], 3))
    with pytest.raises(handler.Unreadable, match="no text"):
        handler.handle_fetched(fetched(volume), MagicMock())
    assert saved == []


def test_the_error_names_the_document_and_correlation_id(volume, saved):
    with pytest.raises(handler.Unreadable) as error:
        handler.handle_fetched(fetched(volume, path=f"{volume}/missing.pdf"), MagicMock())
    assert f"doc_id={DOC_ID} correlationId={CORRELATION_ID}" in str(error.value)


def test_a_database_error_is_not_unreadable(volume, monkeypatch):
    def down(doc, conn):
        raise psycopg.OperationalError("connection refused")

    monkeypatch.setattr(store, "save_document", down)
    with pytest.raises(psycopg.OperationalError):
        handler.handle_fetched(fetched(volume), MagicMock())
