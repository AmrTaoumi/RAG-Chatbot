
import json
import logging
import os
import time

import pika
import psycopg

import handler

logger = logging.getLogger(__name__)

EXCHANGE = "rag.topic"
EXTRACTED_QUEUE = "indexing.documents"
EXTRACTED_KEY = "document.extracted"
INDEXED_KEY = "chunks.indexed"

RETRY_DELAY = 5


def setup(channel):
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    channel.queue_declare(queue=EXTRACTED_QUEUE, durable=True)
    channel.queue_bind(queue=EXTRACTED_QUEUE, exchange=EXCHANGE, routing_key=EXTRACTED_KEY) #put letters labelled document.extracted into indexing.documents.
    channel.confirm_delivery()
    # one message at a time so a crash leaves at most one to be redelivered
    channel.basic_qos(prefetch_count=1)


def on_message(channel, method, body, conn): #runs every time a letter arrives
    try:
        event = handler.handle_extracted(body, conn) # opens the letter (body is the raw JSON), then chunks, embeds and saves. It returns the ChunksIndexed letter to send
    except (handler.Unreadable, psycopg.DataError, psycopg.IntegrityError) as e:
        # the data itself is bad, so retrying would fail the same way and block the queue;
        # connection errors are not caught here, they are retried
        logger.error("discarding message: %s", e)
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return
    # chunksindexed has no consumer yet, so mandatory=False lets RabbitMQ drop it without an error
    channel.basic_publish( # sends chunks indexed letter
        exchange=EXCHANGE,
        routing_key=INDEXED_KEY,
        mandatory=False,
        body=json.dumps(event),
        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
    )
    channel.basic_ack(delivery_tag=method.delivery_tag)


def consume(rabbitmq_url, database_url):
    with psycopg.connect(database_url, autocommit=True, connect_timeout=10) as conn:
        connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
        try:
            channel = connection.channel()
            setup(channel)
            channel.basic_consume(
                queue=EXTRACTED_QUEUE,
                on_message_callback=lambda ch, method, properties, body: on_message(ch, method, body, conn),
            )
            logger.info("waiting for DocumentExtracted events on %s", EXTRACTED_QUEUE)
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