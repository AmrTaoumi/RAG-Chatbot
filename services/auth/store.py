import uuid
import security

def create_user(conn, email, password_hash):
    row = conn.execute(
        "INSERT INTO users (id, email, password_hash) VALUES (%s, %s, %s) "
        "ON CONFLICT (email) DO NOTHING RETURNING id",
        (str(uuid.uuid4()), email, password_hash),
    ).fetchone()
    return row["id"] if row else None


def get_user_by_email(conn, email):
    return conn.execute(
        "SELECT id, email, password_hash FROM users WHERE email = %s",
        (email,),
    ).fetchone()


def get_user_by_id(conn, user_id):
    return conn.execute(
        "SELECT id, email FROM users WHERE id = %s",
        (user_id,),
    ).fetchone()


def save_refresh_token(conn, user_id, token_hash, expires_at):
    conn.execute(
        "INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at) VALUES (%s, %s, %s, %s)",
        (str(uuid.uuid4()), user_id, token_hash, expires_at),
    )

TABLES = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id            TEXT PRIMARY KEY,
        email         TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS refresh_tokens (
        id         TEXT PRIMARY KEY,
        user_id    TEXT NOT NULL REFERENCES users(id),
        token_hash TEXT NOT NULL UNIQUE,
        expires_at TIMESTAMPTZ NOT NULL,
        revoked_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS refresh_tokens_user_id_idx ON refresh_tokens (user_id)",
]


def ensure_tables(conn):
    for sql in TABLES:
        conn.execute(sql)
