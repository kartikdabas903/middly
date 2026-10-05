"""RabbitMQ topology and a thread-safe publisher.

Topology:
    exchange  middly.events  (topic, durable)
    exchange  middly.dlx     (fanout, durable)  -> queue middly.dead-letter
    one durable queue per consumer, each dead-lettering into middly.dlx
"""
from __future__ import annotations

import json
import logging
import threading

import pika
from pika.adapters.blocking_connection import BlockingChannel

from app.core.config import get_settings

logger = logging.getLogger(__name__)

DEAD_LETTER_QUEUE = "middly.dead-letter"


def connection_params() -> pika.URLParameters:
    params = pika.URLParameters(get_settings().rabbitmq_url)
    params.heartbeat = 30
    params.blocked_connection_timeout = 10
    params.connection_attempts = 3
    params.retry_delay = 1
    params.socket_timeout = 5
    return params


def declare_topology(channel: BlockingChannel, consumer_bindings: dict[str, list[str]] | None = None) -> None:
    s = get_settings()
    channel.exchange_declare(s.events_exchange, exchange_type="topic", durable=True)
    channel.exchange_declare(s.events_dlx, exchange_type="fanout", durable=True)
    channel.queue_declare(DEAD_LETTER_QUEUE, durable=True)
    channel.queue_bind(DEAD_LETTER_QUEUE, s.events_dlx)
    for queue, keys in (consumer_bindings or {}).items():
        channel.queue_declare(queue, durable=True, arguments={"x-dead-letter-exchange": s.events_dlx})
        for key in keys:
            channel.queue_bind(queue, s.events_exchange, routing_key=key)


class RabbitPublisher:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._conn: pika.BlockingConnection | None = None
        self._channel: BlockingChannel | None = None

    def _ensure(self) -> BlockingChannel:
        if self._conn is None or self._conn.is_closed or self._channel is None or self._channel.is_closed:
            self._conn = pika.BlockingConnection(connection_params())
            self._channel = self._conn.channel()
            self._channel.confirm_delivery()
            declare_topology(self._channel)
        return self._channel

    def publish(self, routing_key: str, message: dict, *, message_id: str, correlation_id: str | None) -> None:
        body = json.dumps(message, default=str).encode()
        props = pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,
            message_id=message_id,
            correlation_id=correlation_id,
            type=message.get("event_type"),
            headers={"x-retry": 0},
        )
        with self._lock:
            for attempt in (1, 2):
                try:
                    ch = self._ensure()
                    ch.basic_publish(get_settings().events_exchange, routing_key, body, properties=props, mandatory=False)
                    return
                except Exception as exc:
                    logger.warning("Publish attempt %s failed: %s", attempt, exc)
                    self._reset()
                    if attempt == 2:
                        raise

    def queue_depth(self, queue: str) -> int | None:
        with self._lock:
            try:
                ch = self._ensure()
                return ch.queue_declare(queue, passive=True).method.message_count
            except Exception:
                self._reset()
                return None

    def _reset(self) -> None:
        try:
            if self._conn and self._conn.is_open:
                self._conn.close()
        except Exception:
            pass
        self._conn = None
        self._channel = None


publisher = RabbitPublisher()
