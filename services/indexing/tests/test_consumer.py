'''
on_message decides what happens to a letter when handling it fails:
- bad data (unreadable, rejected by the database): log, ack, publish nothing, so it cannot block the queue
- anything else (database down, ...): not acked, the error goes up so the consumer reconnects and retries
'''

from unittest.mock import MagicMock

import psycopg
import pytest

import consumer
import handler


def run(monkeypatch, error):
    def fail(body, conn):
        raise error

    monkeypatch.setattr(handler, "handle_extracted", fail)
    channel, method = MagicMock(), MagicMock()
    consumer.on_message(channel, method, b"{}", MagicMock())
    return channel, method


@pytest.mark.parametrize(
    "error",
    [
        handler.Unreadable("bad message"),
        psycopg.DataError("PostgreSQL text fields cannot contain NUL (0x00) bytes"),
        psycopg.IntegrityError("duplicate key value violates unique constraint"),
    ],
)
def test_bad_data_is_acked_and_nothing_is_published(monkeypatch, error):
    channel, method = run(monkeypatch, error)

    channel.basic_ack.assert_called_once_with(delivery_tag=method.delivery_tag)
    channel.basic_publish.assert_not_called()


def test_database_outage_is_not_acked_so_it_is_retried(monkeypatch):
    channel, method = MagicMock(), MagicMock()
    monkeypatch.setattr(handler, "handle_extracted", MagicMock(side_effect=psycopg.OperationalError("down")))

    with pytest.raises(psycopg.OperationalError):
        consumer.on_message(channel, method, b"{}", MagicMock())

    channel.basic_ack.assert_not_called()
