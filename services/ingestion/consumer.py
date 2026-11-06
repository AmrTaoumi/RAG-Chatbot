import json
import logging
import os
import time

import httpx
import pika

import fetcher

logger = logging.getLogger(__name__)

EXCHANGE = "rag.topic"
DISCOVERED_QUEUE = "ingestion.fetch"
DISCOVERED_KEY = "document.discovered"
FETCHED_QUEUE = "extraction.documents"
FETCHED_KEY = "document.fetched"

RETRY_DELAY = 5


def setup(channel):
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    for queue, key in ((DISCOVERED_QUEUE, DISCOVERED_KEY), (FETCHED_QUEUE, FETCHED_KEY)):
        channel.queue_declare(queue=queue, durable=True)
        channel.queue_bind(queue=queue, exchange=EXCHANGE, routing_key=key)
    channel.confirm_delivery()
    channel.basic_qos(prefetch_count=1)


def on_message(channel, method, body, client, user_agent):
    try:
        event = fetcher.handle_discovered(body, client, user_agent)
    except fetcher.Unreadable as e:
        logger.error("discarding message: %s", e)
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return
    channel.basic_publish(
        exchange=EXCHANGE,
        routing_key=FETCHED_KEY,
        mandatory=True,
        body=json.dumps(event),
        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
    )
    channel.basic_ack(delivery_tag=method.delivery_tag)


def consume(rabbitmq_url, user_agent):
    connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
    try:
        channel = connection.channel()
        setup(channel)
        with httpx.Client(headers={"User-Agent": user_agent}, follow_redirects=True, timeout=60) as client:
            channel.basic_consume(
                queue=DISCOVERED_QUEUE,
                on_message_callback=lambda ch, method, properties, body: on_message(
                    ch, method, body, client, user_agent
                ),
            )
            logger.info("waiting for DocumentDiscovered events on %s", DISCOVERED_QUEUE)
            channel.start_consuming()
    finally:
        if connection.is_open:
            connection.close()


def run():
    rabbitmq_url = os.environ["RABBITMQ_URL"]
    user_agent = os.environ["USER_AGENT"]
    while True:
        try:
            consume(rabbitmq_url, user_agent)
        except Exception as e:
            logger.error("fetcher stopped, retrying in %ds: %r", RETRY_DELAY, e)
            time.sleep(RETRY_DELAY)
