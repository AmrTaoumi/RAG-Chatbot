import json
from unittest.mock import MagicMock

import httpx
import pika
import pytest

import consumer
import fetcher

EVENT = {"eventType": "DocumentFetched", "correlationId": "c", "payload": {"doc_id": "d"}}


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
        {"queue": "ingestion.fetch", "durable": True},
        {"queue": "extraction.documents", "durable": True},
    ]
    bound = [c.kwargs for c in channel.queue_bind.call_args_list]
    assert bound == [
        {"queue": "ingestion.fetch", "exchange": "rag.topic", "routing_key": "document.discovered"},
        {"queue": "extraction.documents", "exchange": "rag.topic", "routing_key": "document.fetched"},
    ]
    channel.confirm_delivery.assert_called_once()
    channel.basic_qos.assert_called_once_with(prefetch_count=1)


def test_on_message_publishes_the_event_and_then_acks(monkeypatch):
    channel = MagicMock()
    seen = []
    monkeypatch.setattr(
        fetcher, "handle_discovered", lambda body, client, ua: seen.append((body, client, ua)) or EVENT
    )

    consumer.on_message(channel, delivery(), b"the body", "client", "UA")

    assert seen == [(b"the body", "client", "UA")]
    call = channel.basic_publish.call_args.kwargs
    assert call["exchange"] == "rag.topic"
    assert call["routing_key"] == "document.fetched"
    assert call["mandatory"] is True
    assert call["properties"].delivery_mode == 2
    assert call["properties"].content_type == "application/json"
    assert json.loads(call["body"]) == EVENT
    channel.basic_ack.assert_called_once_with(delivery_tag=7)
    # the ack comes after the publish, so a failed publish leaves the message to be redelivered
    assert [c[0] for c in channel.method_calls] == ["basic_publish", "basic_ack"]


def test_unreadable_message_is_acked_and_nothing_is_published(monkeypatch, caplog):
    def unreadable(body, client, ua):
        raise fetcher.Unreadable("bad message (doc_id=d correlationId=c)")

    channel = MagicMock()
    monkeypatch.setattr(fetcher, "handle_discovered", unreadable)

    with caplog.at_level("ERROR"):
        consumer.on_message(channel, delivery(), b"x", "client", "UA")

    channel.basic_ack.assert_called_once_with(delivery_tag=7)
    channel.basic_publish.assert_not_called()
    assert "doc_id=d correlationId=c" in caplog.text


def test_network_error_leaves_the_message_unacked(monkeypatch):
    def down(body, client, ua):
        raise httpx.ConnectError("refused")

    channel = MagicMock()
    monkeypatch.setattr(fetcher, "handle_discovered", down)

    with pytest.raises(httpx.ConnectError):
        consumer.on_message(channel, delivery(), b"x", "client", "UA")

    channel.basic_ack.assert_not_called()
    channel.basic_publish.assert_not_called()


def test_unroutable_event_leaves_the_message_unacked(monkeypatch):
    channel = MagicMock()
    channel.basic_publish.side_effect = pika.exceptions.UnroutableError([])
    monkeypatch.setattr(fetcher, "handle_discovered", lambda body, client, ua: EVENT)

    with pytest.raises(pika.exceptions.UnroutableError):
        consumer.on_message(channel, delivery(), b"x", "client", "UA")

    channel.basic_ack.assert_not_called()


def test_consume_sets_up_the_channel_and_waits_for_messages(monkeypatch):
    connection = MagicMock()
    channel = connection.channel.return_value
    monkeypatch.setattr(pika, "BlockingConnection", lambda params: connection)
    handled = []
    monkeypatch.setattr(consumer, "on_message", lambda *args: handled.append(args))

    consumer.consume("amqp://x", "TestBot/1.0")

    kwargs = channel.basic_consume.call_args.kwargs
    assert kwargs["queue"] == "ingestion.fetch"
    kwargs["on_message_callback"]("ch", "method", "props", b"body")
    ch, method, body, client, user_agent = handled[0]
    assert (ch, method, body, user_agent) == ("ch", "method", b"body", "TestBot/1.0")
    assert client.headers["User-Agent"] == "TestBot/1.0"
    channel.start_consuming.assert_called_once()
    connection.close.assert_called_once()


def test_run_retries_after_a_failure(monkeypatch):
    calls = []

    def consume(rabbitmq_url, user_agent):
        calls.append((rabbitmq_url, user_agent))
        if len(calls) == 1:
            raise pika.exceptions.AMQPConnectionError("refused")
        raise KeyboardInterrupt  # ends the loop

    sleeps = []
    monkeypatch.setenv("RABBITMQ_URL", "amqp://x")
    monkeypatch.setenv("USER_AGENT", "TestBot/1.0")
    monkeypatch.setattr(consumer, "consume", consume)
    monkeypatch.setattr(consumer.time, "sleep", sleeps.append)

    with pytest.raises(KeyboardInterrupt):
        consumer.run()

    assert calls == [("amqp://x", "TestBot/1.0")] * 2
    assert sleeps == [consumer.RETRY_DELAY]
