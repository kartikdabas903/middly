"""Generic workflow engine.

Workflow definitions (JSON, versioned in the DB) list typed steps. The engine
persists one workflow_steps row per step and executes automated steps until a
step waits (consent / source outage / officer / citizen / event / external
system) or the workflow completes. All state lives in the database, so any API
process or worker can resume an instance.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.context import get_context
from app.core.errors import InvalidStateError, NotFoundError
from app.core.metrics import APPLICATION_PROCESSING_TIME, WORKFLOW_PROCESSING_TIME
from app.events import outbox
from app.events.types import EventType
from app.models import Application, ApplicationStatusHistory, WorkflowDefinition, WorkflowInstance, WorkflowStep
from app.models.enums import ApplicationStatus, StepStatus, WorkflowStatus
from app.services.audit_service import audit
from app.workflow.handlers import STEP_HANDLERS
from app.workflow.types import StepContext, StepOutcome

logger = logging.getLogger(__name__)

_DONE = {StepStatus.COMPLETED, StepStatus.SKIPPED}


def transition(db: Session, app: Application, new_status: str, *, step: str | None = None, note: str | None = None) -> None:
    """Change the citizen-facing application status and record history."""
    if app.status == new_status and not note:
        return
    ctx = get_context()
    db.add(ApplicationStatusHistory(
        application_id=app.id, from_status=app.status, to_status=new_status, step=step,
        actor=ctx.actor, actor_role=ctx.role, note=note,
    ))
    app.status = new_status


def active_definition(db: Session, code: str) -> WorkflowDefinition:
    wf = db.scalar(select(WorkflowDefinition).where(WorkflowDefinition.code == code, WorkflowDefinition.is_active.is_(True))
                   .order_by(WorkflowDefinition.version.desc()).limit(1))
    if wf is None:
        raise NotFoundError(f"No active workflow definition '{code}'")
    return wf


def validate_definition(definition: dict[str, Any]) -> None:
    steps = definition.get("steps") or []
    if not steps:
        raise ValueError("Workflow must have at least one step")
    keys = [s.get("key") for s in steps]
    if len(keys) != len(set(keys)) or not all(keys):
        raise ValueError("Step keys must be unique and non-empty")
    for s in steps:
        if s.get("type") not in STEP_HANDLERS:
            raise ValueError(f"Unknown step type {s.get('type')!r}")
        if s["type"] == "fetch" and not (s.get("connector") and s.get("category")):
            raise ValueError(f"Fetch step {s['key']} needs connector and category")


class WorkflowEngine:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ lifecycle
    def start(self, application: Application) -> WorkflowInstance:
        definition = active_definition(self.db, application.service.workflow_code)
        instance = WorkflowInstance(definition_id=definition.id, application_id=application.id, status=WorkflowStatus.RUNNING, context={})
        instance.definition = definition
        self.db.add(instance)
        for seq, step_def in enumerate(definition.definition["steps"], start=1):
            instance.steps.append(WorkflowStep(
                step_key=step_def["key"], step_type=step_def["type"], label=step_def.get("label", step_def["key"]),
                sequence=seq, status=StepStatus.PENDING, output={},
            ))
        self.db.flush()
        audit("WORKFLOW_STARTED", "workflow_instance", str(instance.id), details={
            "workflow": definition.code, "version": definition.version, "application": application.application_number})
        return self.advance(instance)

    def instance_for(self, application: Application) -> WorkflowInstance:
        inst = self.db.scalar(select(WorkflowInstance).where(WorkflowInstance.application_id == application.id))
        if inst is None:
            raise NotFoundError("Workflow instance not found")
        return inst

    def _step_def(self, instance: WorkflowInstance, key: str) -> dict[str, Any]:
        return next(s for s in instance.definition.definition["steps"] if s["key"] == key)

    def advance(self, instance: WorkflowInstance) -> WorkflowInstance:
        """Execute automated steps until the workflow waits or completes."""
        if instance.status in (WorkflowStatus.COMPLETED, WorkflowStatus.CANCELLED):
            return instance
        app = self.db.get(Application, instance.application_id)
        started = time.perf_counter()
        instance.status = WorkflowStatus.RUNNING
        for _ in range(len(instance.steps) + 2):
            step = next((s for s in instance.steps if s.status not in _DONE), None)
            if step is None:
                self._complete(instance, app)
                break
            outcome = self._execute(instance, step, app)
            if outcome.kind == "COMPLETED":
                continue
            if outcome.kind == "DECIDED":
                self._apply_decision(instance, app, step, outcome.decision, outcome.reason, decided_by="SYSTEM")
                continue
            break  # WAIT
        WORKFLOW_PROCESSING_TIME.labels(instance.definition.code, instance.status).observe(time.perf_counter() - started)
        self.db.flush()
        return instance

    def _execute(self, instance: WorkflowInstance, step: WorkflowStep, app: Application) -> StepOutcome:
        step_def = self._step_def(instance, step.step_key)
        handler = STEP_HANDLERS[step.step_type]
        now = clock.now()
        step.status = StepStatus.IN_PROGRESS
        step.started_at = step.started_at or now
        step.attempts += 1
        instance.current_step_key = step.step_key
        app.current_step = step.step_key
        ctx = StepContext(self.db, instance, step, step_def, app, app.service)
        try:
            outcome = handler.execute(ctx)
        except Exception as exc:  # unexpected failure: park the step, never lose state
            logger.exception("Step %s failed", step.step_key)
            outcome = StepOutcome.wait(WorkflowStatus.WAITING_FOR_SOURCE, app_status=ApplicationStatus.WAITING_FOR_SOURCE,
                                       error=f"Unexpected error: {exc}"[:500])
        step.output = {**(step.output or {}), **outcome.output} if outcome.kind == "WAIT" else outcome.output
        if outcome.kind in ("COMPLETED", "DECIDED"):
            step.status = StepStatus.COMPLETED
            step.completed_at = clock.now()
            step.error = None
            if outcome.app_status:
                transition(self.db, app, outcome.app_status, step=step.step_key, note=outcome.note)
            elif outcome.note:
                transition(self.db, app, app.status, step=step.step_key, note=outcome.note)
        else:
            step.status = StepStatus.WAITING
            step.error = outcome.error
            instance.status = outcome.wait_status or WorkflowStatus.RUNNING
            instance.last_error = outcome.error
            if outcome.app_status and (outcome.app_status != app.status or outcome.note and step.attempts == 1):
                transition(self.db, app, outcome.app_status, step=step.step_key, note=outcome.note)
        return outcome

    def _apply_decision(self, instance: WorkflowInstance, app: Application, from_step: WorkflowStep, decision: str, reason: str | None, decided_by: str) -> None:
        now = clock.now()
        decision_step = None
        for s in instance.steps:
            if s.sequence <= from_step.sequence or s.status in _DONE:
                continue
            if s.step_type == "decision":
                decision_step = s
                break
            s.status = StepStatus.SKIPPED
            s.completed_at = now
            s.output = {"skipped_because": f"Decision {decision} reached at {from_step.step_key}"}
        if decision_step is not None:
            decision_step.status = StepStatus.COMPLETED
            decision_step.started_at = decision_step.started_at or now
            decision_step.completed_at = now
            decision_step.attempts += 1
            decision_step.output = {"decision": decision, "reason": reason, "decided_by": decided_by}
        self._record_decision(instance, app, decision, reason, decided_by)

    def _record_decision(self, instance: WorkflowInstance, app: Application, decision: str, reason: str | None, decided_by: str) -> None:
        now = clock.now()
        status = {"APPROVED": ApplicationStatus.APPROVED, "REJECTED": ApplicationStatus.REJECTED, "RESOLVED": ApplicationStatus.RESOLVED}[decision]
        app.decision = decision
        app.decision_reason = reason
        app.decided_by = decided_by
        app.decided_at = now
        app.processing_seconds = round((now - app.submitted_at).total_seconds(), 1)
        transition(self.db, app, status, step="DECISION", note=reason)
        APPLICATION_PROCESSING_TIME.labels(app.service.code, decision).observe(app.processing_seconds)
        event_type = {
            "APPROVED": EventType.APPLICATION_APPROVED,
            "REJECTED": EventType.APPLICATION_REJECTED,
            "RESOLVED": EventType.GRIEVANCE_RESOLVED,
        }[decision]
        outbox.emit(self.db, event_type, aggregate_type="application", aggregate_id=str(app.id), payload={
            "application_id": str(app.id), "application_number": app.application_number, "citizen_id": app.citizen_id,
            "service": app.service.name, "department": app.department.name, "decision": decision, "reason": reason,
            "decided_by": decided_by, "department_reference": app.department_reference, "notify_step": "NOTIFICATION_SENT",
        })

    def _complete(self, instance: WorkflowInstance, app: Application) -> None:
        if instance.status != WorkflowStatus.COMPLETED:
            instance.status = WorkflowStatus.COMPLETED
            instance.completed_at = clock.now()
            instance.current_step_key = None
            instance.last_error = None
            audit("WORKFLOW_COMPLETED", "workflow_instance", str(instance.id), details={"application": app.application_number, "status": app.status})

    # ------------------------------------------------------------------ external triggers
    def officer_decision(self, instance: WorkflowInstance, decision: str, remarks: str | None, officer: str) -> WorkflowInstance:
        if instance.status != WorkflowStatus.WAITING_FOR_OFFICER:
            raise InvalidStateError(f"Application is not awaiting officer review (workflow state: {instance.status})")
        app = self.db.get(Application, instance.application_id)
        review = next((s for s in instance.steps if s.step_type == "human_review" and s.status == StepStatus.WAITING), None)
        if review is None:
            raise InvalidStateError("No review step is waiting")
        review.status = StepStatus.COMPLETED
        review.completed_at = clock.now()
        review.output = {**(review.output or {}), "action": decision, "remarks": remarks, "officer": officer}
        self._apply_decision(instance, app, review, decision, remarks, decided_by=officer)
        return self.advance(instance)

    def request_clarification(self, instance: WorkflowInstance, question: str, officer: str) -> None:
        if instance.status != WorkflowStatus.WAITING_FOR_OFFICER:
            raise InvalidStateError("Clarification can only be requested during officer review")
        app = self.db.get(Application, instance.application_id)
        review = next(s for s in instance.steps if s.step_type == "human_review" and s.status == StepStatus.WAITING)
        thread = list((review.output or {}).get("clarifications", []))
        thread.append({"question": question, "asked_by": officer, "asked_at": clock.now().isoformat(), "response": None})
        review.output = {**(review.output or {}), "clarifications": thread}
        instance.status = WorkflowStatus.WAITING_FOR_CITIZEN
        transition(self.db, app, ApplicationStatus.CLARIFICATION_REQUESTED, step=review.step_key, note=question)
        outbox.emit(self.db, EventType.CLARIFICATION_REQUESTED, aggregate_type="application", aggregate_id=str(app.id), payload={
            "application_id": str(app.id), "application_number": app.application_number, "citizen_id": app.citizen_id,
            "question": question, "department": app.department.name,
        })

    def citizen_clarification_response(self, instance: WorkflowInstance, response: str) -> None:
        if instance.status != WorkflowStatus.WAITING_FOR_CITIZEN:
            raise InvalidStateError("No clarification is pending")
        app = self.db.get(Application, instance.application_id)
        review = next(s for s in instance.steps if s.step_type == "human_review" and s.status == StepStatus.WAITING)
        thread = list((review.output or {}).get("clarifications", []))
        if thread and thread[-1].get("response") is None:
            thread[-1] = {**thread[-1], "response": response, "responded_at": clock.now().isoformat()}
        review.output = {**(review.output or {}), "clarifications": thread}
        instance.status = WorkflowStatus.WAITING_FOR_OFFICER
        transition(self.db, app, ApplicationStatus.UNDER_REVIEW, step=review.step_key, note="Citizen responded to clarification")

    def complete_event_step(self, instance: WorkflowInstance, step_key: str, output: dict[str, Any]) -> WorkflowInstance:
        step = next((s for s in instance.steps if s.step_key == step_key), None)
        if step is None or step.status in _DONE:
            return instance
        step.status = StepStatus.COMPLETED
        step.started_at = step.started_at or clock.now()
        step.completed_at = clock.now()
        step.attempts = max(1, step.attempts)
        step.output = output
        return self.advance(instance)

    def cancel(self, instance: WorkflowInstance, reason: str) -> None:
        app = self.db.get(Application, instance.application_id)
        for s in instance.steps:
            if s.status not in _DONE:
                s.status = StepStatus.SKIPPED
                s.output = {**(s.output or {}), "skipped_because": reason}
        instance.status = WorkflowStatus.CANCELLED
        instance.completed_at = clock.now()
        transition(self.db, app, ApplicationStatus.WITHDRAWN, note=reason)
