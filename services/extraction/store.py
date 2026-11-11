from psycopg.types.json import Jsonb


def ensure_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            doc_id       TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            url          TEXT NOT NULL,
            page_count   INTEGER NOT NULL,
            pages        JSONB NOT NULL,
            extracted_at TIMESTAMPTZ NOT NULL
        )
        """
    )


def save_document(doc, conn):
    # a repeated DocumentFetched replaces the row instead of adding a second one
    conn.execute(
        """
        INSERT INTO documents (doc_id, title, url, page_count, pages, extracted_at)
        VALUES (%s, %s, %s, %s, %s, now())
        ON CONFLICT (doc_id) DO UPDATE SET
            title = EXCLUDED.title,
            url = EXCLUDED.url,
            page_count = EXCLUDED.page_count,
            pages = EXCLUDED.pages,
            extracted_at = EXCLUDED.extracted_at
        """,
        (doc["doc_id"], doc["title"], doc["url"], doc["page_count"], Jsonb(doc["pages"])),
    )


def list_documents(conn):
    rows = conn.execute(
        "SELECT doc_id, title, url, page_count, extracted_at FROM documents ORDER BY extracted_at, doc_id"
    ).fetchall()
    return [
        {
            "doc_id": doc_id,
            "title": title,
            "url": url,
            "page_count": page_count,
            "extracted_at": extracted_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        for doc_id, title, url, page_count, extracted_at in rows
    ]
