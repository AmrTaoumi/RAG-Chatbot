from datetime import datetime, timezone
from unittest.mock import MagicMock

import store

DOC = {
    "doc_id": "9e107d9d372bb6826bd81d3542a419d6",
    "title": "Academic Integrity Regulations",
    "url": "https://x.example/a.pdf",
    "page_count": 2,
    "pages": [{"page": 1, "text": "one"}, {"page": 2, "text": "two"}],
}


def test_ensure_table_creates_documents_keyed_by_doc_id():
    conn = MagicMock()
    store.ensure_table(conn)
    sql = conn.execute.call_args.args[0]
    assert "CREATE TABLE IF NOT EXISTS documents" in sql
    assert "doc_id       TEXT PRIMARY KEY" in sql


def test_save_document_updates_the_row_when_doc_id_exists():
    conn = MagicMock()
    store.save_document(DOC, conn)
    sql, params = conn.execute.call_args.args
    assert "ON CONFLICT (doc_id) DO UPDATE" in sql
    assert params[:4] == (DOC["doc_id"], DOC["title"], DOC["url"], 2)
    assert params[4].obj == DOC["pages"]


def test_list_documents_returns_the_contract_shape():
    conn = MagicMock()
    when = datetime(2026, 10, 20, 12, 1, 0, tzinfo=timezone.utc)
    conn.execute.return_value.fetchall.return_value = [
        (DOC["doc_id"], DOC["title"], DOC["url"], 2, when)
    ]
    assert store.list_documents(conn) == [
        {
            "doc_id": DOC["doc_id"],
            "title": DOC["title"],
            "url": DOC["url"],
            "page_count": 2,
            "extracted_at": "2026-10-20T12:01:00Z",
        }
    ]
