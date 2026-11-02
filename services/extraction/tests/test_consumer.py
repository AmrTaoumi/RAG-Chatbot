import json
from unittest.mock import MagicMock

import pika
import psycopg
import pytest

import consumer
import handler

EVENT = {"eventType": "DocumentExtracted", "correlationId": "c", "payload": {"doc_id": "d"}}


def delivery():
    method = MagicMock()
    method.delivery_tag = 7
    return method


def test_setup_declares_both_queues_with_their_bindings():
    channel = MagicMock()

    consumer.setup(channel)

    channel.exchange_declare.assert_called_once_with(
        exchange="rag.topic", exchange_type="topic", durable=True
    )
    declared = [c.kwargs for c in channel.queue_declare.call_args_list]
    assert declared == [
        {"queue": "extraction.documents", "durable": True},
        {"queue": "indexing.documents", "durable": True},
    ]
    bound = [c.kwargs for c in channel.queue_bind.call_args_list]
    assert bound == [
        {"queue": "extraction.documents", "exchange": "rag.topic", "routing_key": "document.fetched"},
        {"queue": "indexing.documents", "exchange": "rag.topic", "routing_key": "document.extracted"},
    ]
    channel.confirm_delivery.assert_called_once()
    channel.basic_qos.assert_called_once_with(prefetch_count=1)


def test_on_message_publishes_the_event_and_then_acks(monkeypatch):
    channel = MagicMock()
    conn = MagicMock()
    seen = []
    monkeypatch.setattr(handler, "handle_fetched", lambda body, c: seen.append((body, c)) or EVENT)

    consumer.on_message(channel, delivery(), b"the body", conn)

    assert seen == [(b"the body", conn)]
    call = channel.basic_publish.call_args.kwargs
    assert call["exchange"] == "rag.topic"
    assert call["routing_key"] == "document.extracted"
    assert call["mandatory"] is True
    assert call["properties"].delivery_mode == 2
    assert call["properties"].content_type == "application/json"
    assert json.loads(call["body"]) == EVENT
    channel.basic_ack.assert_called_once_with(delivery_tag=7)
    # the ack comes after the publish, so a failed publish leaves the message to be redelivered
    assert [c[0] for c in channel.method_calls] == ["basic_publish", "basic_ack"]


def test_unreadable_message_is_acked_and_nothing_is_published(monkeypatch, caplog):
    def unreadable(body, conn):
        raise handler.Unreadable("bad message (doc_id=d correlationId=c)")

    channel = MagicMock()
    monkeypatch.setattr(handler, "handle_fetched", unreadable)

    with caplog.at_level("ERROR"):
        consumer.on_message(channel, delivery(), b"x", MagicMock())

    channel.basic_ack.assert_called_once_with(delivery_tag=7)
    channel.basic_publish.assert_not_called()
    assert "doc_id=d correlationId=c" in caplog.text


def test_database_error_leaves_the_message_unacked(monkeypatch):
    def down(body, conn):
        raise psycopg.OperationalError("connection refused")

    channel = MagicMock()
    monkeypatch.setattr(handler, "handle_fetched", down)

    with pytest.raises(psycopg.OperationalError):
        consumer.on_message(channel, delivery(), b"x", MagicMock())

    channel.basic_ack.assert_not_called()
    channel.basic_publish.assert_not_called()


def test_unroutable_event_leaves_the_message_unacked(monkeypatch):
    channel = MagicMock()
    channel.basic_publish.side_effect = pika.exceptions.UnroutableError([])
    monkeypatch.setattr(handler, "handle_fetched", lambda body, c: EVENT)

    with pytest.raises(pika.exceptions.UnroutableError):
        consumer.on_message(channel, delivery(), b"x", MagicMock())

    channel.basic_ack.assert_not_called()


def test_consume_sets_up_the_channel_and_waits_for_messages(monkeypatch):
    conn = MagicMock()
    conn.__enter__.return_value = conn
    connection = MagicMock()
    channel = connection.channel.return_value
    ensured = []
    monkeypatch.setattr(psycopg, "connect", lambda *a, **kw: conn)
    monkeypatch.setattr(pika, "BlockingConnection", lambda params: connection)
    monkeypatch.setattr(consumer.store, "ensure_table", lambda c: ensured.append(c))
    handled = []
    monkeypatch.setattr(consumer, "on_message", lambda *args: handled.append(args))

    consumer.consume("amqp://x", "postgresql://x")

    assert ensured == [conn]
    kwargs = channel.basic_consume.call_args.kwargs
    assert kwargs["queue"] == "extraction.documents"
    kwargs["on_message_callback"]("ch", "method", "props", b"body")
    assert handled == [("ch", "method", b"body", conn)]
    channel.start_consuming.assert_called_once()
    connection.close.assert_called_once()


def test_run_retries_after_a_failure(monkeypatch):
    calls = []

    def consume(rabbitmq_url, database_url):
        calls.append((rabbitmq_url, database_url))
        if len(calls) == 1:
            raise pika.exceptions.AMQPConnectionError("refused")
        raise KeyboardInterrupt  # ends the loop

    sleeps = []
    monkeypatch.setenv("RABBITMQ_URL", "amqp://x")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setattr(consumer, "consume", consume)
    monkeypatch.setattr(consumer.time, "sleep", sleeps.append)

    with pytest.raises(KeyboardInterrupt):
        consumer.run()

    assert calls == [("amqp://x", "postgresql://x")] * 2
    assert sleeps == [consumer.RETRY_DELAY]
