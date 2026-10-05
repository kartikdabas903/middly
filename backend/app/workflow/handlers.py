"""Step-type handlers. The engine maps the `type` in a workflow definition to one
of these. Handlers know nothing about specific departments: connectors and data
categories come from the workflow definition / service configuration.

To add a new step type, implement `execute(ctx) -> StepOutcome` and register it
in `STEP_HANDLERS`.
"""
from __future__ import annotations

import logging

from app.core import clock
from app.core.errors import ConsentRequiredError
from app.eligibility.engine import evaluate
from app.events import outbox
from app.events.types import EventType
from app.integration.errors import ConnectorError
from app.models.enums import ApplicationStatus, WorkflowStatus
from app.services import connector_service, consent_service, data_access_service
from app.services.audit_service import audit
from app.workflow.types import StepContext, StepOutcome

logger = logging.getLogger(__name__)


class StartHandler:
    def execute(self, ctx: StepContext) -> StepOutcome:
        app = ctx.application
        event_type = ctx.step_def.get("event", EventType.APPLICATION_CREATED)
        outbox.emit(ctx.db, event_type, aggregate_type="application", aggregate_id=str(app.id), payload={
            "application_id": str(app.id), "application_number": app.application_number, "citizen_id": app.citizen_id,
            "service": ctx.service.code, "department": app.department.name,
        })
        return StepOutcome.completed({"form_fields": sorted(app.form_data.keys()), "submitted_at": app.submitted_at.isoformat()})


class ConsentHandler:
    def execute(self, ctx: StepContext) -> StepOutcome:
        categories = ctx.step_def.get("categories") or ctx.service.required_categories
        consent = consent_service.has_consent_for(
            ctx.db, citizen_id=ctx.application.citizen_id, department_id=ctx.application.department_id,
            categories=categories, application_id=ctx.application.id,
        )
        if consent is None:
            return StepOutcome.wait(
                WorkflowStatus.WAITING_FOR_CONSENT, app_status=ApplicationStatus.CONSENT_PENDING,
                output={"requested_categories": categories, "purpose": ctx.service.consent_purpose},
                note="Waiting for citizen consent",
            )
        ctx.application.consent_id = consent.id
        return StepOutcome.completed(
            {"consent_id": str(consent.id), "categories": consent.data_categories, "expires_at": consent.expires_at.isoformat()},
            app_status=ApplicationStatus.PROCESSING, note="Consent granted",
        )


class FetchHandler:
    def execute(self, ctx: StepContext) -> StepOutcome:
        app, category, key = ctx.application, ctx.step_def["category"], ctx.step_def["connector"]
        try:
            result = data_access_service.fetch_category(
                ctx.db, citizen_id=app.citizen_id, category=category, connector_key=key,
                purpose=ctx.service.consent_purpose, requester_department_id=app.department_id,
                requester_name=app.department.name, application_id=app.id,
            )
        except ConsentRequiredError as exc:
            return StepOutcome.wait(WorkflowStatus.WAITING_FOR_CONSENT, app_status=ApplicationStatus.CONSENT_PENDING, error=exc.message,
                                    note=f"Consent for {category} data is no longer active")
        except ConnectorError as exc:
            row = connector_service.get_row(ctx.db, key)
            retry_after = getattr(exc, "retry_after_seconds", 0)
            first_failure = ctx.step.attempts <= 1
            if first_failure:
                outbox.emit(ctx.db, EventType.SOURCE_UNAVAILABLE, aggregate_type="application", aggregate_id=str(app.id), payload={
                    "application_id": str(app.id), "application_number": app.application_number, "citizen_id": app.citizen_id,
                    "system": row.system_name, "reason": exc.reason,
                })
            return StepOutcome.wait(
                WorkflowStatus.WAITING_FOR_SOURCE, app_status=ApplicationStatus.WAITING_FOR_SOURCE,
                output={"category": category, "connector": key, "system": row.system_name, "unavailable": True,
                        "reason": exc.reason, "retry_after_seconds": retry_after, "last_attempt_at": clock.now().isoformat()},
                error=exc.message, note=f"{row.system_name} temporarily unavailable",
            )
        outbox.emit(ctx.db, EventType.DATA_FETCHED, aggregate_type="application", aggregate_id=str(app.id), payload={
            "application_id": str(app.id), "category": category, "system": result.system_name, "found": result.found,
        })
        return StepOutcome.completed(result.to_output(), app_status=ApplicationStatus.PROCESSING)


class ValidationHandler:
    def execute(self, ctx: StepContext) -> StepOutcome:
        outputs = ctx.outputs_of("fetch")
        merged, report = data_access_service.consolidate(ctx.db, ctx.application.citizen_id, outputs, application_id=ctx.application.id)
        sources = [
            {"category": o["category"], "system": o["system"], "connector": o["connector"], "found": o.get("found", True),
             "fetched_at": o.get("fetched_at"), "source_updated_at": o.get("source_updated_at"), "source_reference": o.get("source_reference")}
            for o in outputs
        ]
        ctx.application.profile_snapshot = {**merged.to_dict(), "sources": sources}
        ctx.application.data_quality = report.to_dict()
        return StepOutcome.completed({"overall": report.overall, "counts": report.to_dict()["counts"], "sources": report.source_status})


class EligibilityHandler:
    def execute(self, ctx: StepContext) -> StepOutcome:
        ruleset = ctx.service.eligibility_rules or {"code": "NONE", "rules": []}
        result = evaluate(ruleset, ctx.application.profile_snapshot or {}, on=clock.now().date())
        ctx.application.eligibility_result = result.to_dict()
        outbox.emit(ctx.db, EventType.ELIGIBILITY_COMPLETED, aggregate_type="application", aggregate_id=str(ctx.application.id), payload={
            "application_id": str(ctx.application.id), "eligible": result.eligible,
            "passed_rules": result.passed_rules, "failed_rules": result.failed_rules,
        })
        audit("SYSTEM_EVALUATED_ELIGIBILITY", "application", str(ctx.application.id), details={
            "eligible": result.eligible, "failed_rules": result.failed_rules, "ruleset": result.ruleset})
        output = {"eligible": result.eligible, "passed_rules": result.passed_rules, "failed_rules": result.failed_rules}
        if not result.eligible and ctx.step_def.get("on_ineligible", "AUTO_REJECT") == "AUTO_REJECT":
            return StepOutcome.decided("REJECTED", "Not eligible: " + "; ".join(result.reasons), output)
        return StepOutcome.completed(output)


class DepartmentSubmitHandler:
    def execute(self, ctx: StepContext) -> StepOutcome:
        app, svc = ctx.application, ctx.service
        key = ctx.step_def.get("connector") or svc.department_connector_key
        if not key:
            return StepOutcome.completed({"skipped": "No department system configured"})
        profile = app.profile_snapshot or {}
        payload = {
            "citizen_id": app.citizen_id,
            "full_name": profile.get("full_name") or "Applicant",
            "service_code": svc.code,
            "application_number": app.application_number,
            "form": app.form_data,
            "eligible": (app.eligibility_result or {}).get("eligible"),
        }
        row = connector_service.get_row(ctx.db, key)
        try:
            result = connector_service.invoke(ctx.db, key, "submit_application", payload, application_id=app.id, citizen_id=app.citizen_id)
        except ConnectorError as exc:
            audit("SYSTEM_FORWARD_FAILED", "application", str(app.id), status="FAILURE", destination_system=row.system_name, details={"error": exc.message})
            return StepOutcome.wait(WorkflowStatus.WAITING_FOR_SOURCE, app_status=ApplicationStatus.WAITING_FOR_SOURCE,
                                    output={"system": row.system_name, "connector": key, "unavailable": True, "reason": exc.reason},
                                    error=exc.message, note=f"{row.system_name} temporarily unavailable")
        app.department_reference = result["reference"]
        audit("SYSTEM_FORWARDED_APPLICATION", "application", str(app.id), source_system="Middly Platform", destination_system=row.system_name,
              details={"department_reference": result["reference"]})
        if svc.workflow_code != "GRIEVANCE_REDRESSAL":
            outbox.emit(ctx.db, EventType.APPLICATION_SUBMITTED, aggregate_type="application", aggregate_id=str(app.id), payload={
                "application_id": str(app.id), "application_number": app.application_number, "citizen_id": app.citizen_id,
                "department": app.department.name, "department_reference": result["reference"],
            })
        return StepOutcome.completed({"system": row.system_name, "reference": result["reference"], "department_status": result.get("status")},
                                     app_status=ApplicationStatus.FORWARDED_TO_DEPARTMENT, note=f"Forwarded to {row.system_name} ({result['reference']})")


class HumanReviewHandler:
    def execute(self, ctx: StepContext) -> StepOutcome:
        return StepOutcome.wait(WorkflowStatus.WAITING_FOR_OFFICER, app_status=ApplicationStatus.UNDER_REVIEW,
                                output={"queue": ctx.application.department.name, "role": ctx.step_def.get("role", "OFFICER")},
                                note="Awaiting officer review")


class DecisionHandler:
    def execute(self, ctx: StepContext) -> StepOutcome:
        # Decisions are recorded by the engine (officer action or an early DECIDED outcome).
        return StepOutcome.wait(WorkflowStatus.WAITING_FOR_OFFICER, app_status=ApplicationStatus.UNDER_REVIEW)


class NotificationHandler:
    def execute(self, ctx: StepContext) -> StepOutcome:
        # Completed asynchronously by the notification consumer (event-driven).
        return StepOutcome.wait(WorkflowStatus.WAITING_FOR_EVENT, output={"awaiting": "NOTIFICATION_REQUESTED"})


class ExternalStatusHandler:
    """Polls the department system for status (used by grievances)."""

    def execute(self, ctx: StepContext) -> StepOutcome:
        app = ctx.application
        key = ctx.step_def.get("connector") or ctx.service.department_connector_key
        try:
            result = connector_service.invoke(ctx.db, key, "get_application", app.department_reference, application_id=app.id)
        except ConnectorError as exc:
            return StepOutcome.wait(WorkflowStatus.WAITING_FOR_EXTERNAL, output={**ctx.step.output, "sync_error": exc.message,
                                                                                 "last_sync_at": clock.now().isoformat()}, error=exc.message)
        status = result["status"]
        output = {"external_status": status, "assigned_to": result.get("assigned_to"), "remarks": result.get("remarks"),
                  "history": result.get("history", []), "last_sync_at": clock.now().isoformat()}
        if status in ctx.step_def.get("complete_on", []):
            return StepOutcome.decided("RESOLVED", result.get("remarks") or "Resolved by department", output)
        if status in ctx.step_def.get("reject_on", []):
            return StepOutcome.decided("REJECTED", result.get("remarks") or "Closed by department", output)
        app_status = ApplicationStatus.IN_PROGRESS if status in {"ASSIGNED", "IN_PROGRESS"} else ApplicationStatus.FORWARDED_TO_DEPARTMENT
        return StepOutcome.wait(WorkflowStatus.WAITING_FOR_EXTERNAL, app_status=app_status, output=output,
                                note=f"Department status: {status.replace('_', ' ').title()}")


STEP_HANDLERS = {
    "start": StartHandler(),
    "consent": ConsentHandler(),
    "fetch": FetchHandler(),
    "validation": ValidationHandler(),
    "eligibility": EligibilityHandler(),
    "department_submit": DepartmentSubmitHandler(),
    "human_review": HumanReviewHandler(),
    "decision": DecisionHandler(),
    "notification": NotificationHandler(),
    "external_status": ExternalStatusHandler(),
}
