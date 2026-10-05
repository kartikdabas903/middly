"""Application lifecycle and unified tracking."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import ConflictError, DomainValidationError, ForbiddenError, InvalidStateError, NotFoundError
from app.core.security import Principal, Role
from app.models import Application, ApplicationSequence, Consent, Department, Service, WorkflowInstance
from app.models.enums import ApplicationStatus, ConsentStatus, StepStatus, TERMINAL_APPLICATION_STATUSES, WorkflowStatus
from app.services import consent_service, data_access_service
from app.services.audit_service import audit
from app.workflow.engine import WorkflowEngine, transition

# --------------------------------------------------------------------------- helpers


def next_application_number(db: Session) -> str:
    year = clock.now().year
    seq = db.get(ApplicationSequence, year, with_for_update=True)
    if seq is None:
        seq = ApplicationSequence(year=year, last_value=0)
        db.add(seq)
        db.flush()
        seq = db.get(ApplicationSequence, year, with_for_update=True)
    seq.last_value += 1
    return f"APP-{year}-{seq.last_value:04d}"


def get_service(db: Session, code: str) -> Service:
    svc = db.scalar(select(Service).where(Service.code == code, Service.is_active.is_(True)))
    if svc is None:
        raise NotFoundError(f"Service {code} not found")
    return svc


def validate_form(service: Service, form: dict[str, Any]) -> dict[str, Any]:
    """Server-side validation against the service's declarative form schema."""
    cleaned: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for field in service.form_schema.get("fields", []):
        name = field["name"]
        value = form.get(name)
        if isinstance(value, str):
            value = value.strip()
        if value in (None, ""):
            if field.get("required"):
                errors[name] = "This field is required"
            continue
        if field["type"] == "select":
            allowed = {o["value"] for o in field.get("options", [])}
            if value not in allowed:
                errors[name] = "Invalid option"
                continue
        if field["type"] in ("text", "textarea"):
            if not isinstance(value, str):
                errors[name] = "Must be text"
                continue
            if len(value) < field.get("minLength", 0):
                errors[name] = f"Must be at least {field['minLength']} characters"
                continue
            if len(value) > field.get("maxLength", 5000):
                errors[name] = f"Must be at most {field['maxLength']} characters"
                continue
        cleaned[name] = value
    unknown = set(form) - {f["name"] for f in service.form_schema.get("fields", [])}
    if unknown:
        errors["_"] = f"Unknown fields: {sorted(unknown)}"
    if errors:
        raise DomainValidationError("Application form is invalid", details=errors)
    return cleaned


def load(db: Session, app_id: str) -> Application:
    try:
        app = db.get(Application, uuid.UUID(str(app_id)))
    except ValueError:
        app = db.scalar(select(Application).where(Application.application_number == str(app_id)))
    if app is None:
        raise NotFoundError("Application not found")
    return app


def authorize_view(principal: Principal, app: Application) -> None:
    if principal.is_platform_admin:
        return
    if Role.CITIZEN in principal.roles and principal.citizen_id == app.citizen_id:
        return
    if principal.has_any(Role.OFFICER, Role.DEPARTMENT_ADMIN) and principal.department_code == app.department.code:
        return
    raise ForbiddenError("You are not allowed to access this application")


def authorize_officer(principal: Principal, app: Application) -> None:
    if not principal.has_any(Role.OFFICER, Role.DEPARTMENT_ADMIN):
        raise ForbiddenError("Only department officers can take decisions")
    if principal.department_code != app.department.code:
        raise ForbiddenError("This application belongs to another department")


def _owner(principal: Principal, app: Application) -> None:
    if principal.citizen_id != app.citizen_id:
        raise ForbiddenError("Only the applicant can perform this action")


# --------------------------------------------------------------------------- commands


def create(db: Session, principal: Principal, service_code: str, form: dict[str, Any]) -> Application:
    if not principal.citizen_id:
        raise ForbiddenError("Only citizens with a linked citizen ID can apply")
    service = get_service(db, service_code)
    cleaned = validate_form(service, form)
    active = db.scalar(select(Application).where(
        Application.citizen_id == principal.citizen_id,
        Application.service_id == service.id,
        Application.status.notin_([s.value for s in TERMINAL_APPLICATION_STATUSES]),
    ))
    if active is not None:
        raise ConflictError(f"You already have an active application ({active.application_number}) for this service",
                            details={"application_id": str(active.id), "application_number": active.application_number})
    data_access_service.ensure_citizen(db, principal.citizen_id)
    app = Application(
        id=uuid.uuid4(),
        application_number=next_application_number(db),
        citizen_id=principal.citizen_id,
        service_id=service.id,
        department_id=service.department_id,
        status=ApplicationStatus.SUBMITTED,
        form_data=cleaned,
        created_by=principal.username,
        submitted_at=clock.now(),
    )
    app.service = service
    app.department = service.department
    db.add(app)
    db.flush()
    transition(db, app, ApplicationStatus.SUBMITTED, step="APPLICATION_CREATED", note="Application submitted by citizen")
    audit("CITIZEN_SUBMITTED_APPLICATION", "application", str(app.id), destination_system=service.department.name,
          details={"application_number": app.application_number, "service": service.code})
    WorkflowEngine(db).start(app)
    return app


def grant_consent(db: Session, principal: Principal, app: Application, categories: list[str]) -> Consent:
    _owner(principal, app)
    return consent_service.grant_for_application(db, principal, app, categories)


def process(db: Session, principal: Principal, app: Application) -> Application:
    """Run (or resume) automated processing: consent check, data fetch, validation, eligibility."""
    authorize_view(principal, app)
    engine = WorkflowEngine(db)
    instance = engine.instance_for(app)
    if instance.status not in (WorkflowStatus.WAITING_FOR_CONSENT, WorkflowStatus.WAITING_FOR_SOURCE, WorkflowStatus.RUNNING):
        raise InvalidStateError(f"Nothing to process (workflow state: {instance.status})")
    if instance.status == WorkflowStatus.WAITING_FOR_SOURCE:
        audit("APPLICATION_RETRY_REQUESTED", "application", str(app.id), details={"step": instance.current_step_key})
    engine.advance(instance)
    return app


def sync_external(db: Session, principal: Principal | None, app: Application) -> Application:
    if principal:
        authorize_view(principal, app)
    engine = WorkflowEngine(db)
    instance = engine.instance_for(app)
    if instance.status == WorkflowStatus.WAITING_FOR_EXTERNAL:
        engine.advance(instance)
    return app


def officer_action(db: Session, principal: Principal, app: Application, action: str, remarks: str | None) -> Application:
    authorize_officer(principal, app)
    engine = WorkflowEngine(db)
    instance = engine.instance_for(app)
    if action in ("APPROVE", "REJECT"):
        if action == "REJECT" and not (remarks and remarks.strip()):
            raise DomainValidationError("A reason is required to reject an application")
        if action == "APPROVE":
            # Approval requires that the citizen's consent is still active.
            if consent_service.has_consent_for(db, citizen_id=app.citizen_id, department_id=app.department_id,
                                               categories=app.service.required_categories, application_id=app.id) is None and app.service.required_categories:
                raise InvalidStateError("Citizen consent is no longer active; the application cannot be approved")
        decision = "APPROVED" if action == "APPROVE" else "REJECTED"
        engine.officer_decision(instance, decision, remarks, officer=principal.username)
        audit(f"OFFICER_{decision}_APPLICATION", "application", str(app.id), details={"application_number": app.application_number, "remarks": remarks})
    elif action == "REQUEST_CLARIFICATION":
        if not (remarks and remarks.strip()):
            raise DomainValidationError("Please enter the clarification question")
        engine.request_clarification(instance, remarks.strip(), officer=principal.username)
        audit("OFFICER_REQUESTED_CLARIFICATION", "application", str(app.id), details={"question": remarks})
    else:
        raise DomainValidationError(f"Unknown action {action}")
    return app


def respond_clarification(db: Session, principal: Principal, app: Application, response: str) -> Application:
    _owner(principal, app)
    if not response.strip():
        raise DomainValidationError("Response cannot be empty")
    engine = WorkflowEngine(db)
    engine.citizen_clarification_response(engine.instance_for(app), response.strip()[:2000])
    audit("CITIZEN_RESPONDED_CLARIFICATION", "application", str(app.id))
    return app


def withdraw(db: Session, principal: Principal, app: Application, reason: str | None) -> Application:
    _owner(principal, app)
    if app.status in TERMINAL_APPLICATION_STATUSES:
        raise InvalidStateError("Application is already closed")
    engine = WorkflowEngine(db)
    engine.cancel(engine.instance_for(app), reason or "Withdrawn by citizen")
    for consent in db.scalars(select(Consent).where(Consent.application_id == app.id, Consent.status == ConsentStatus.ACTIVE)):
        consent.status = ConsentStatus.REVOKED
        consent.revoked_at = clock.now()
        consent.revocation_reason = "Application withdrawn"
    audit("CITIZEN_WITHDREW_APPLICATION", "application", str(app.id), details={"reason": reason})
    return app


# --------------------------------------------------------------------------- queries


def list_for(db: Session, principal: Principal, *, status: str | None = None, service: str | None = None,
             q: str | None = None, limit: int = 50, offset: int = 0) -> tuple[list[Application], int]:
    stmt = select(Application)
    if principal.is_platform_admin:
        pass
    elif principal.has_any(Role.OFFICER, Role.DEPARTMENT_ADMIN):
        stmt = stmt.join(Department, Application.department_id == Department.id).where(Department.code == principal.department_code)
    elif principal.citizen_id:
        stmt = stmt.where(Application.citizen_id == principal.citizen_id)
    else:
        return [], 0
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        stmt = stmt.where(Application.status.in_(statuses))
    if service:
        stmt = stmt.join(Service, Application.service_id == Service.id).where(Service.code == service)
    if q:
        stmt = stmt.where(or_(Application.application_number.ilike(f"%{q}%"), Application.citizen_id.ilike(f"%{q}%")))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Application.updated_at.desc()).limit(limit).offset(offset)).unique().all()
    return list(rows), total


NEXT_ACTION = {
    ApplicationStatus.SUBMITTED: "Platform is preparing your application",
    ApplicationStatus.CONSENT_PENDING: "Citizen to grant data-sharing consent",
    ApplicationStatus.PROCESSING: "Platform is verifying data with departments",
    ApplicationStatus.WAITING_FOR_SOURCE: "Waiting for a department system to become available (automatic retry)",
    ApplicationStatus.FORWARDED_TO_DEPARTMENT: "Department to register the application",
    ApplicationStatus.UNDER_REVIEW: "Officer review",
    ApplicationStatus.CLARIFICATION_REQUESTED: "Citizen to respond to the officer's question",
    ApplicationStatus.IN_PROGRESS: "Department is working on the request",
    ApplicationStatus.APPROVED: "No action needed — department will contact you with batch details",
    ApplicationStatus.REJECTED: "No further action",
    ApplicationStatus.RESOLVED: "No further action",
    ApplicationStatus.WITHDRAWN: "No further action",
}


def summary(app: Application, instance: WorkflowInstance | None = None) -> dict[str, Any]:
    current_label = None
    if instance is not None and instance.current_step_key:
        current_label = next((s.label for s in instance.steps if s.step_key == instance.current_step_key), None)
    return {
        "id": str(app.id),
        "application_number": app.application_number,
        "citizen_id": app.citizen_id,
        "applicant_name": (app.profile_snapshot or {}).get("full_name"),
        "service_code": app.service.code,
        "service": app.service.name,
        "department": app.department.name,
        "department_code": app.department.code,
        "status": app.status,
        "current_step": app.current_step,
        "current_step_label": current_label,
        "workflow_status": instance.status if instance else None,
        "submitted_at": app.submitted_at,
        "updated_at": app.updated_at,
        "decision": app.decision,
        "eligible": (app.eligibility_result or {}).get("eligible"),
        "data_quality": (app.data_quality or {}).get("overall"),
        "expected_next_action": NEXT_ACTION.get(app.status, ""),
        "department_reference": app.department_reference,
    }


def instances_for(db: Session, apps: list[Application]) -> dict[uuid.UUID, WorkflowInstance]:
    if not apps:
        return {}
    rows = db.scalars(select(WorkflowInstance).where(WorkflowInstance.application_id.in_([a.id for a in apps]))).all()
    return {r.application_id: r for r in rows}


def _timeline(instance: WorkflowInstance) -> list[dict[str, Any]]:
    out = []
    for s in instance.steps:
        state = {
            StepStatus.COMPLETED: "done", StepStatus.SKIPPED: "skipped", StepStatus.WAITING: "current",
            StepStatus.IN_PROGRESS: "current", StepStatus.FAILED: "failed",
        }.get(s.status, "pending")
        if s.status == StepStatus.WAITING and (s.output or {}).get("unavailable"):
            state = "blocked"
        out.append({
            "key": s.step_key, "type": s.step_type, "label": s.label, "status": s.status, "state": state,
            "attempts": s.attempts, "started_at": s.started_at, "completed_at": s.completed_at, "error": s.error,
            "detail": _step_detail(s),
        })
    return out


def _step_detail(step) -> dict[str, Any]:
    o = step.output or {}
    if step.step_type == "fetch":
        return {k: o.get(k) for k in ("system", "category", "found", "fetched_at", "unavailable", "reason", "retry_after_seconds", "source_reference") if k in o}
    if step.step_type in ("human_review", "decision"):
        return {k: o.get(k) for k in ("action", "remarks", "officer", "decision", "reason", "decided_by", "clarifications") if k in o}
    if step.step_type == "eligibility":
        return {k: o.get(k) for k in ("eligible", "passed_rules", "failed_rules")}
    if step.step_type == "validation":
        return {"overall": o.get("overall"), "counts": o.get("counts")}
    if step.step_type == "department_submit":
        return {k: o.get(k) for k in ("system", "reference", "unavailable", "reason") if k in o}
    if step.step_type == "external_status":
        return {k: o.get(k) for k in ("external_status", "assigned_to", "remarks", "last_sync_at", "sync_error") if k in o}
    if step.step_type == "consent":
        return {k: o.get(k) for k in ("consent_id", "categories", "requested_categories", "expires_at") if k in o}
    if step.step_type == "notification":
        return {k: o.get(k) for k in ("notification_title", "delivered_at", "channel") if k in o}
    return {}


def _sources(instance: WorkflowInstance) -> list[dict[str, Any]]:
    sources = []
    for s in instance.steps:
        if s.step_type != "fetch":
            continue
        o = s.output or {}
        if s.status == StepStatus.COMPLETED:
            state = "VERIFIED" if o.get("found", True) else "NOT_FOUND"
        elif s.status == StepStatus.WAITING and o.get("unavailable"):
            state = "UNAVAILABLE"
        elif s.status == StepStatus.SKIPPED:
            state = "SKIPPED"
        else:
            state = "PENDING"
        sources.append({
            "step": s.step_key, "category": o.get("category") or s.step_key.replace("FETCH_", ""), "system": o.get("system") or s.label,
            "connector": o.get("connector"), "state": state, "fetched_at": o.get("fetched_at"), "attempts": s.attempts,
            "error": s.error, "retry_after_seconds": o.get("retry_after_seconds"),
        })
    return sources


def detail(db: Session, principal: Principal, app: Application) -> dict[str, Any]:
    authorize_view(principal, app)
    instance = db.scalar(select(WorkflowInstance).where(WorkflowInstance.application_id == app.id))
    data = summary(app, instance)
    is_owner = principal.citizen_id == app.citizen_id
    is_officer = principal.has_any(Role.OFFICER, Role.DEPARTMENT_ADMIN) and principal.department_code == app.department.code

    # Data visibility: owner always; department staff only while consent is active (checked & logged per category).
    profile_visible, profile_reason = True, None
    if not is_owner and not is_officer:
        profile_visible, profile_reason = False, "Personal data is visible only to the citizen and the processing department"
    elif not is_owner and app.service.required_categories and app.profile_snapshot:
        try:
            for cat in app.service.required_categories:
                consent_service.verify(db, citizen_id=app.citizen_id, department_id=app.department_id, category=cat,
                                       purpose="Officer review of application", application_id=app.id)
        except Exception:
            profile_visible, profile_reason = False, "Citizen consent is not active — consolidated data is hidden"
    consent = db.get(Consent, app.consent_id) if app.consent_id else None
    if consent:
        consent_service._expire_if_needed(consent)

    review_step = next((s for s in (instance.steps if instance else []) if s.step_type == "human_review"), None)
    data.update({
        "form_data": app.form_data,
        "decision_reason": app.decision_reason,
        "decided_by": app.decided_by,
        "decided_at": app.decided_at,
        "processing_seconds": app.processing_seconds,
        "eligibility": app.eligibility_result,
        "data_quality_report": app.data_quality,
        "profile": (app.profile_snapshot if profile_visible else None),
        "profile_hidden_reason": profile_reason,
        "timeline": _timeline(instance) if instance else [],
        "sources": _sources(instance) if instance else [],
        "history": [
            {"from_status": h.from_status, "to_status": h.to_status, "step": h.step, "actor": h.actor, "actor_role": h.actor_role,
             "note": h.note, "at": h.created_at}
            for h in app.history
        ],
        "workflow": {
            "instance_id": str(instance.id) if instance else None,
            "definition": instance.definition.code if instance else None,
            "version": instance.definition.version if instance else None,
            "status": instance.status if instance else None,
            "last_error": instance.last_error if instance else None,
        },
        "consent": consent_service.serialize(db, consent) if consent else None,
        "consent_request": {
            "department": app.department.name,
            "categories": app.service.required_categories,
            "purpose": app.service.consent_purpose,
            "validity_days": app.service.consent_validity_days,
        } if app.service.required_categories else None,
        "clarifications": (review_step.output or {}).get("clarifications", []) if review_step else [],
        "permissions": {
            "can_grant_consent": is_owner and instance is not None and instance.status == WorkflowStatus.WAITING_FOR_CONSENT,
            "can_retry": instance is not None and instance.status == WorkflowStatus.WAITING_FOR_SOURCE and (is_owner or principal.is_staff),
            "can_decide": is_officer and instance is not None and instance.status == WorkflowStatus.WAITING_FOR_OFFICER,
            "can_respond": is_owner and instance is not None and instance.status == WorkflowStatus.WAITING_FOR_CITIZEN,
            "can_withdraw": is_owner and app.status not in TERMINAL_APPLICATION_STATUSES,
            "can_sync": instance is not None and instance.status == WorkflowStatus.WAITING_FOR_EXTERNAL,
        },
    })
    if not is_owner:
        audit("OFFICER_VIEWED_APPLICATION" if is_officer else "ADMIN_VIEWED_APPLICATION", "application", str(app.id),
              details={"application_number": app.application_number, "profile_visible": profile_visible})
    return data
