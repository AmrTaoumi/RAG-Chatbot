import json
import logging
import os
import time

import pika
import psycopg

import handler
import store

logger = logging.getLogger(__name__)

EXCHANGE = "rag.topic"
FETCHED_QUEUE = "extraction.documents"
FETCHED_KEY = "document.fetched"
EXTRACTED_QUEUE = "indexing.documents"
EXTRACTED_KEY = "document.extracted"

RETRY_DELAY = 5


def setup(channel):
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    for queue, key in ((FETCHED_QUEUE, FETCHED_KEY), (EXTRACTED_QUEUE, EXTRACTED_KEY)):
        channel.queue_declare(queue=queue, durable=True)
        channel.queue_bind(queue=queue, exchange=EXCHANGE, routing_key=key)
    channel.confirm_delivery()
    # one message at a time so a crash leaves at most one to be redelivered
    channel.basic_qos(prefetch_count=1)


def on_message(channel, method, body, conn):
    try:
        event = handler.handle_fetched(body, conn)
    except handler.Unreadable as e:
        logger.error("discarding message: %s", e)
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return
    channel.basic_publish(
        exchange=EXCHANGE,
        routing_key=EXTRACTED_KEY,
        mandatory=True,
        body=json.dumps(event),
        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
    )
    channel.basic_ack(delivery_tag=method.delivery_tag)


def consume(rabbitmq_url, database_url):
    with psycopg.connect(database_url, autocommit=True, connect_timeout=10) as conn:
        store.ensure_table(conn)
        connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
        try:
            channel = connection.channel()
            setup(channel)
            channel.basic_consume(
                queue=FETCHED_QUEUE,
                on_message_callback=lambda ch, method, properties, body: on_message(ch, method, body, conn),
            )
            logger.info("waiting for DocumentFetched events on %s", FETCHED_QUEUE)
            channel.start_consuming()
        finally:
            if connection.is_open:
                connection.close()


def run():
    rabbitmq_url = os.environ["RABBITMQ_URL"]
    database_url = os.environ["DATABASE_URL"]
    while True:
        try:
            consume(rabbitmq_url, database_url)
        except Exception as e:
            logger.error("consumer stopped, retrying in %ds: %r", RETRY_DELAY, e)
            time.sleep(RETRY_DELAY)
