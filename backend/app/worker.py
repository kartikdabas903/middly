"""Middly worker: RabbitMQ consumers + background jobs.

    python -m app.worker

Consumers (one durable queue each, dead-lettering to middly.dlx):
    event-log, notification-dispatcher, notification-service, department-sync
Background jobs:
    outbox relay        re-publish events stuck in PENDING
    health monitor      periodic connector health checks
    auto-retry          resume workflows WAITING_FOR_SOURCE (bounded attempts)
    status sync         poll department systems for WAITING_FOR_EXTERNAL workflows
"""
from __future__ import annotations

import json
import logging
import signal
import threading
import time
import uuid
from datetime import timedelta

import pika
from prometheus_client import start_http_server
from sqlalchemy import select

from app.core import clock
from app.core.config import get_settings
from app.core.context import system_context
from app.core.logging import configure_logging
from app.db.session import get_sessionmaker
from app.events.handlers import CONSUMERS, Consumer, mark_event, process_message
from app.events.outbox import relay_pending
from app.events.rabbit import connection_params, declare_topology
from app.integration.registry import registry
from app.models import WorkflowInstance
from app.models.enums import EventStatus, WorkflowStatus
from app.services import connector_service
from app.workflow.engine import WorkflowEngine

logger = logging.getLogger("middly.worker")
MAX_DELIVERY_ATTEMPTS = 3
_stop = threading.Event()


# ----------------------------------------------------------------------------- background jobs

def _loop(name: str, interval: float, fn) -> None:
    while not _stop.is_set():
        try:
            with system_context(actor=f"SYSTEM:{name}"):
                fn()
        except Exception:
            logger.exception("Background job %s failed", name)
        _stop.wait(interval)


def job_health() -> None:
    with get_sessionmaker()() as db:
        connector_service.run_health_checks(db)
        db.commit()


def job_auto_retry() -> None:
    s = get_settings()
    cutoff = clock.now() - timedelta(seconds=s.auto_retry_interval_seconds)
    with get_sessionmaker()() as db:
        ids = db.scalars(select(WorkflowInstance.id).where(
            WorkflowInstance.status == WorkflowStatus.WAITING_FOR_SOURCE,
            WorkflowInstance.updated_at < cutoff,
            WorkflowInstance.auto_retry_count < s.auto_retry_max_attempts,
        )).all()
    for instance_id in ids:
        with get_sessionmaker()() as db:
            inst = db.get(WorkflowInstance, instance_id, with_for_update={"skip_locked": True})
            if inst is None or inst.status != WorkflowStatus.WAITING_FOR_SOURCE:
                continue
            inst.auto_retry_count += 1
            logger.info("Auto-retrying workflow %s (attempt %s)", instance_id, inst.auto_retry_count)
            WorkflowEngine(db).advance(inst)
            db.commit()


def job_status_sync() -> None:
    with get_sessionmaker()() as db:
        ids = db.scalars(select(WorkflowInstance.id).where(WorkflowInstance.status == WorkflowStatus.WAITING_FOR_EXTERNAL)).all()
    for instance_id in ids:
        with get_sessionmaker()() as db:
            inst = db.get(WorkflowInstance, instance_id)
            if inst and inst.status == WorkflowStatus.WAITING_FOR_EXTERNAL:
                WorkflowEngine(db).advance(inst)
                db.commit()


# ----------------------------------------------------------------------------- consumers

def _on_message(channel, method, properties, body, consumer: Consumer) -> None:
    try:
        message = json.loads(body)
    except ValueError:
        logger.error("Discarding malformed message on %s", consumer.queue)
        channel.basic_nack(method.delivery_tag, requeue=False)
        return
    attempt = int((properties.headers or {}).get("x-retry", 0))
    try:
        process_message(consumer, message)
        channel.basic_ack(method.delivery_tag)
    except Exception as exc:
        if attempt + 1 < MAX_DELIVERY_ATTEMPTS:
            delay = 2 ** attempt
            logger.warning("%s failed for %s (attempt %s): %s — retrying in %ss", consumer.name, message.get("event_type"), attempt + 1, exc, delay)
            time.sleep(delay)
            props = pika.BasicProperties(content_type="application/json", delivery_mode=2, message_id=properties.message_id,
                                         correlation_id=properties.correlation_id, type=properties.type, headers={"x-retry": attempt + 1})
            channel.basic_publish("", consumer.queue, body, properties=props)
            channel.basic_ack(method.delivery_tag)
        else:
            logger.error("%s exhausted retries for event %s — dead-lettering", consumer.name, message.get("event_id"))
            channel.basic_nack(method.delivery_tag, requeue=False)
            mark_event(uuid.UUID(message["event_id"]), EventStatus.DEAD_LETTERED, f"{consumer.name}: {exc}")


def consume_forever() -> None:
    bindings = {c.queue: c.routing_keys for c in CONSUMERS}
    while not _stop.is_set():
        try:
            conn = pika.BlockingConnection(connection_params())
            ch = conn.channel()
            declare_topology(ch, bindings)
            ch.basic_qos(prefetch_count=10)
            for consumer in CONSUMERS:
                ch.basic_consume(consumer.queue, lambda c, m, p, b, cons=consumer: _on_message(c, m, p, b, cons))
            logger.info("Worker consuming from %s", ", ".join(bindings))
            while not _stop.is_set():
                conn.process_data_events(time_limit=1)
            conn.close()
        except pika.exceptions.AMQPError as exc:
            logger.warning("RabbitMQ connection lost (%s); reconnecting in 3s", exc)
            _stop.wait(3)


def main() -> None:
    s = get_settings()
    configure_logging(s.log_level)
    registry.discover()
    start_http_server(s.worker_metrics_port)
    signal.signal(signal.SIGTERM, lambda *_: _stop.set())
    signal.signal(signal.SIGINT, lambda *_: _stop.set())
    jobs = [
        ("outbox-relay", s.outbox_relay_interval_seconds, relay_pending),
        ("health-monitor", s.health_check_interval_seconds, job_health),
        ("auto-retry", 30, job_auto_retry),
        ("status-sync", 45, job_status_sync),
    ]
    for name, interval, fn in jobs:
        threading.Thread(target=_loop, args=(name, interval, fn), name=name, daemon=True).start()
    consume_forever()


if __name__ == "__main__":
    main()
