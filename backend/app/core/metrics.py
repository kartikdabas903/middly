"""Prometheus metrics. Names follow the platform observability spec."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

NS = "middly"

REQUEST_COUNT = Counter(
    "request_count", "HTTP requests handled", ["method", "route", "status"], namespace=NS
)
REQUEST_LATENCY = Histogram(
    "request_latency_seconds",
    "HTTP request latency",
    ["method", "route"],
    namespace=NS,
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
CONNECTOR_SUCCESS = Counter(
    "connector_success_count", "Successful connector calls", ["connector", "operation"], namespace=NS
)
CONNECTOR_FAILURE = Counter(
    "connector_failure_count", "Failed connector calls", ["connector", "operation", "reason"], namespace=NS
)
CONNECTOR_LATENCY = Histogram(
    "connector_latency_seconds", "Connector call latency", ["connector", "operation"], namespace=NS,
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8),
)
CONNECTOR_UP = Gauge(
    "connector_up", "Connector health (1 healthy, 0.5 degraded, 0 down)", ["connector"], namespace=NS
)
WORKFLOW_PROCESSING_TIME = Histogram(
    "workflow_processing_time_seconds", "Time spent executing automated workflow steps",
    ["workflow", "outcome"], namespace=NS, buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)
APPLICATION_PROCESSING_TIME = Histogram(
    "application_processing_time_seconds", "Submission-to-decision time of applications",
    ["service", "decision"], namespace=NS,
    buckets=(1, 10, 60, 300, 900, 3600, 86400, 604800),
)
EVENT_PROCESSING = Counter(
    "event_processing_count", "Events processed by consumers", ["event_type", "consumer", "result"], namespace=NS
)
EVENTS_PUBLISHED = Counter(
    "events_published_count", "Events published to the broker", ["event_type"], namespace=NS
)
APPLICATIONS_BY_STATUS = Gauge(
    "applications", "Applications by status and department", ["status", "department"], namespace=NS
)
WORKFLOW_INSTANCES_BY_STATUS = Gauge(
    "workflow_instances", "Workflow instances by status", ["status"], namespace=NS
)
