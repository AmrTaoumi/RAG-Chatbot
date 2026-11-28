from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import main
import store


def executed_sql(conn):
    return [call.args[0] for call in conn.execute.call_args_list]


def test_ensure_tables_creates_users_before_refresh_tokens():
    conn = MagicMock()
    store.ensure_tables(conn)
    sql = executed_sql(conn)
    users = next(i for i, s in enumerate(sql) if "CREATE TABLE IF NOT EXISTS users" in s)
    tokens = next(i for i, s in enumerate(sql) if "CREATE TABLE IF NOT EXISTS refresh_tokens" in s)
    assert users < tokens


def test_users_table_has_unique_email_and_no_plaintext_password():
    conn = MagicMock()
    store.ensure_tables(conn)
    users = next(s for s in executed_sql(conn) if "TABLE IF NOT EXISTS users" in s)
    assert "id            TEXT PRIMARY KEY" in users
    assert "email         TEXT NOT NULL UNIQUE" in users
    assert "password_hash TEXT NOT NULL" in users
    assert "password " not in users


def test_refresh_tokens_reference_users_and_store_only_a_unique_hash():
    conn = MagicMock()
    store.ensure_tables(conn)
    tokens = next(s for s in executed_sql(conn) if "TABLE IF NOT EXISTS refresh_tokens" in s)
    assert "user_id    TEXT NOT NULL REFERENCES users(id)" in tokens
    assert "token_hash TEXT NOT NULL UNIQUE" in tokens
    assert "revoked_at TIMESTAMPTZ," in tokens


def test_every_statement_is_safe_to_rerun():
    conn = MagicMock()
    store.ensure_tables(conn)
    assert all("IF NOT EXISTS" in s for s in executed_sql(conn))


def test_startup_creates_tables(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    connect = MagicMock()
    monkeypatch.setattr(main.psycopg, "connect", connect)
    calls = []
    monkeypatch.setattr(main.store, "ensure_tables", calls.append)
    key = object()
    monkeypatch.setattr(main, "load_private_key", lambda path: key)

    with TestClient(main.app):
        pass

    assert main.app.state.private_key is key

    assert connect.call_args.args == ("postgresql://test",)
    assert calls == [connect.return_value.__enter__.return_value]


def test_create_user_skips_duplicate_email_and_returns_none():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    assert store.create_user(conn, "a@lancaster.ac.uk", "hash") is None
    sql, values = conn.execute.call_args.args
    assert "ON CONFLICT (email) DO NOTHING" in sql
    assert "RETURNING id" in sql
    assert values[1:] == ("a@lancaster.ac.uk", "hash")


def test_create_user_returns_new_id():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"id": "u123"}
    assert store.create_user(conn, "a@lancaster.ac.uk", "hash") == "u123"


def test_save_refresh_token_stores_the_hash_it_is_given():
    conn = MagicMock()
    store.save_refresh_token(conn, "u123", "token-hash", "2026-12-01")
    sql, values = conn.execute.call_args.args
    assert "INSERT INTO refresh_tokens" in sql
    assert values[1:] == ("u123", "token-hash", "2026-12-01")