from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import main
import store


def executed_sql(conn):
    return [call.args[0] for call in conn.execute.call_args_list]


def test_ensure_tables_creates_conversations_before_messages():
    conn = MagicMock()
    store.ensure_tables(conn)
    sql = executed_sql(conn)
    conversations = next(i for i, s in enumerate(sql) if "CREATE TABLE IF NOT EXISTS conversations" in s)
    messages = next(i for i, s in enumerate(sql) if "CREATE TABLE IF NOT EXISTS messages" in s)
    assert conversations < messages


def test_conversations_user_id_has_no_fk_to_auth_users():
    conn = MagicMock()
    store.ensure_tables(conn)
    conversations = next(s for s in executed_sql(conn) if "TABLE IF NOT EXISTS conversations" in s)
    assert "user_id    TEXT NOT NULL," in conversations
    assert "REFERENCES" not in conversations


def test_messages_cascade_with_their_conversation():
    conn = MagicMock()
    store.ensure_tables(conn)
    messages = next(s for s in executed_sql(conn) if "TABLE IF NOT EXISTS messages" in s)
    assert "REFERENCES conversations(id) ON DELETE CASCADE" in messages
    assert "CHECK (role IN ('user', 'assistant'))" in messages
    assert "citations       JSONB" in messages


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

    with TestClient(main.app):
        pass

    assert connect.call_args.args == ("postgresql://test",)
    assert calls == [connect.return_value.__enter__.return_value]
