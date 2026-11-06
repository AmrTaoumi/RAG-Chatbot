from unittest.mock import MagicMock

import store

CHUNKS = [
    {
        "chunk_id": "d-p1-c0",
        "doc_id": "d",
        "title": "Title",
        "url": "https://x.example/a.pdf",
        "page": 1,
        "text": "one",
        "embedding": "[0.5,-0.25]",
    }
]


def test_replace_chunks_deletes_the_old_rows_before_inserting():
    conn = MagicMock()
    store.replace_chunks(conn, "d", CHUNKS)

    cur = conn.cursor.return_value.__enter__.return_value
    assert cur.execute.call_args.args == ("DELETE FROM chunks WHERE doc_id = %s", ("d",))
    sql, rows = cur.executemany.call_args.args
    assert "INSERT INTO chunks" in sql
    assert "%(embedding)s::vector" in sql
    assert rows == CHUNKS
    calls = [call[0] for call in cur.mock_calls]
    assert calls.index("execute") < calls.index("executemany")


def test_replace_chunks_runs_in_one_transaction():
    conn = MagicMock()
    store.replace_chunks(conn, "d", CHUNKS)
    conn.transaction.assert_called_once()