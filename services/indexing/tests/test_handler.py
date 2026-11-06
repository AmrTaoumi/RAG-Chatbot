'''
The 4 tests check, :
- the outgoing letter has the right shape
- every chunk gets its embedding
-an empty page gives 0 chunks
- 8 kinds of broken letter all raise Unreadable, and nothing gets saved

'''



import json
import uuid
from unittest.mock import MagicMock

import pytest

import handler
import store

DOC_ID = "9e107d9d372bb6826bd81d3542a419d6"
CORRELATION_ID = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


@pytest.fixture(autouse=True)
def fake_embed(monkeypatch):
    monkeypatch.setattr(handler, "embed", lambda texts: [[0.5, -0.25]] * len(texts))


@pytest.fixture
def saved(monkeypatch):
    saved = []
    monkeypatch.setattr(store, "replace_chunks", lambda conn, doc_id, chunks: saved.append((doc_id, chunks)))
    return saved


def extracted(**payload):
    fields = {
        "doc_id": DOC_ID,
        "url": "https://x.example/a.pdf",
        "title": "Academic Integrity Regulations",
        "page_count": 2,
        "pages": [
            {"page": 1, "text": "Students must submit their work on time."},
            {"page": 2, "text": "Late work is penalised."},
        ],
    }
    return json.dumps(
        {
            "eventType": "DocumentExtracted",
            "eventId": "3f2b8c1e-5d0a-4c1e-9a7b-1e2d3c4b5a63",
            "timestamp": "2026-10-20T12:01:00Z",
            "correlationId": CORRELATION_ID,
            "payload": {**fields, **payload},
        }
    )


def test_handle_extracted_builds_the_chunks_indexed_event(saved):
    event = handler.handle_extracted(extracted(), MagicMock())

    assert event["eventType"] == "ChunksIndexed"
    assert event["correlationId"] == CORRELATION_ID
    assert event["timestamp"].endswith("Z")
    assert uuid.UUID(event["eventId"]) != uuid.UUID("3f2b8c1e-5d0a-4c1e-9a7b-1e2d3c4b5a63")
    assert event["payload"] == {"doc_id": DOC_ID, "chunk_count": 2}


def test_handle_extracted_stores_every_chunk_with_its_embedding(saved):
    handler.handle_extracted(extracted(), MagicMock())

    doc_id, chunks = saved[0]
    assert doc_id == DOC_ID
    assert [chunk["chunk_id"] for chunk in chunks] == [f"{DOC_ID}-p1-c0", f"{DOC_ID}-p2-c0"]
    assert all(chunk["embedding"] == "[0.5,-0.25]" for chunk in chunks)


def test_document_with_no_text_indexes_zero_chunks(saved):
    event = handler.handle_extracted(extracted(pages=[{"page": 1, "text": "   "}]), MagicMock())

    assert event["payload"]["chunk_count"] == 0
    assert saved[0] == (DOC_ID, [])


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        json.dumps({**json.loads(extracted()), "eventType": "DocumentFetched"}),
        extracted(doc_id=""),
        extracted(title=None),
        extracted(pages="text"),
        extracted(pages=[{"page": "1", "text": "x"}]),
        extracted(pages=[{"page": 1}]),
        extracted(pages=[{"page": 1, "text": "a"}, {"page": 1, "text": "b"}]),
    ],
)
def test_bad_messages_are_unreadable_and_nothing_is_stored(body, saved):
    with pytest.raises(handler.Unreadable):
        handler.handle_extracted(body, MagicMock())
    assert saved == []
