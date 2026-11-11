
'''
This script seeds the PostgreSQL database with some document chunks
It reads chunks from a seed_chunk JSON file, generates an embedding for each chunk,
and inserts the chunks and their embeddings into the database. existing chunks 
are not inserted again because of ON CONFLICT DO NOTHING.'''


import json
import os

import psycopg

from main import embed

INSERT_SQL = """
    INSERT INTO chunks (chunk_id, doc_id, title, url, page, text, embedding)
    VALUES (%(chunk_id)s, %(doc_id)s, %(title)s, %(url)s, %(page)s, %(text)s, %(embedding)s::vector)
    ON CONFLICT (chunk_id) DO NOTHING
"""


def seed(path="seed/seed_chunks.json"):
    with open(path) as f:
        chunks = json.load(f)

    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=10) as conn:
        for chunk in chunks:
            vector = embed(chunk["text"])
            chunk["embedding"] = "[" + ",".join(str(x) for x in vector) + "]"
            conn.execute(INSERT_SQL, chunk)
    print(f"seeded {len(chunks)} chunks")


if __name__ == "__main__":
    seed()