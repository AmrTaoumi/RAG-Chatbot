INSERT_CHUNK = """
    INSERT INTO chunks (chunk_id, doc_id, title, url, page, text, embedding)
    VALUES (%(chunk_id)s, %(doc_id)s, %(title)s, %(url)s, %(page)s, %(text)s, %(embedding)s::vector)
"""


def replace_chunks(conn, doc_id, chunks):
    # delete then insert in one transaction, so a redelivered message replaces the
    # document's chunks instead of duplicating them, and a crash leaves the old ones
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))
            cur.executemany(INSERT_CHUNK, chunks)
