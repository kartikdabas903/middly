"""Read-side repositories used by the API routers."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import (
    Application,
    AuditLog,
    Connector,
    ConnectorCall,
    Consent,
    DataQualityIssue,
    Event,
    Notification,
    WorkflowDefinition,
    WorkflowInstance,
)
from app.repositories.base import paginate


class AuditRepository:
    @staticmethod
    def search(db: Session, *, action: str | None = None, actor: str | None = None, resource: str | None = None,
               resource_id: str | None = None, correlation_id: str | None = None, status: str | None = None,
               since: datetime | None = None, until: datetime | None = None, limit: int = 50, offset: int = 0):
        stmt = select(AuditLog)
        if action:
            stmt = stmt.where(AuditLog.action.ilike(f"%{action}%"))
        if actor:
            stmt = stmt.where(AuditLog.actor.ilike(f"%{actor}%"))
        if resource:
            stmt = stmt.where(AuditLog.resource == resource)
        if resource_id:
            stmt = stmt.where(AuditLog.resource_id == resource_id)
        if correlation_id:
            stmt = stmt.where(AuditLog.correlation_id == correlation_id)
        if status:
            stmt = stmt.where(AuditLog.status == status)
        if since:
            stmt = stmt.where(AuditLog.timestamp >= since)
        if until:
            stmt = stmt.where(AuditLog.timestamp <= until)
        return paginate(db, stmt, limit=limit, offset=offset, order_by=AuditLog.id.desc())

    @staticmethod
    def actions(db: Session) -> list[str]:
        return list(db.scalars(select(AuditLog.action).distinct().order_by(AuditLog.action)))


class EventRepository:
    @staticmethod
    def search(db: Session, *, event_type: str | None, status: str | None, aggregate_id: str | None, limit: int, offset: int):
        stmt = select(Event)
        if event_type:
            stmt = stmt.where(Event.event_type == event_type)
        if status:
            stmt = stmt.where(Event.status == status)
        if aggregate_id:
            stmt = stmt.where(Event.aggregate_id == aggregate_id)
        return paginate(db, stmt, limit=limit, offset=offset, order_by=Event.created_at.desc())


class NotificationRepository:
    @staticmethod
    def for_citizen(db: Session, citizen_id: str, *, unread_only: bool, limit: int, offset: int):
        stmt = select(Notification).where(Notification.citizen_id == citizen_id)
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        return paginate(db, stmt, limit=limit, offset=offset, order_by=Notification.created_at.desc())

    @staticmethod
    def unread_count(db: Session, citizen_id: str) -> int:
        return db.scalar(select(func.count()).where(Notification.citizen_id == citizen_id, Notification.read_at.is_(None))) or 0


class DataQualityRepository:
    @staticmethod
    def search(db: Session, *, status: str | None, issue_type: str | None, severity: str | None, citizen_id: str | None, limit: int, offset: int):
        stmt = select(DataQualityIssue)
        if status:
            stmt = stmt.where(DataQualityIssue.status == status)
        if issue_type:
            stmt = stmt.where(DataQualityIssue.issue_type == issue_type)
        if severity:
            stmt = stmt.where(DataQualityIssue.severity == severity)
        if citizen_id:
            stmt = stmt.where(DataQualityIssue.citizen_id == citizen_id)
        return paginate(db, stmt, limit=limit, offset=offset, order_by=DataQualityIssue.detected_at.desc())

    @staticmethod
    def summary(db: Session) -> dict:
        by_source = [
            {"source_system": s, "open": int(o), "total": int(t)}
            for s, o, t in db.execute(
                select(DataQualityIssue.source_system,
                       func.sum(case((DataQualityIssue.status == "OPEN", 1), else_=0)),
                       func.count()).group_by(DataQualityIssue.source_system))
        ]
        by_type = [{"issue_type": t, "count": n} for t, n in db.execute(
            select(DataQualityIssue.issue_type, func.count()).where(DataQualityIssue.status == "OPEN").group_by(DataQualityIssue.issue_type))]
        return {"by_source": by_source, "open_by_type": by_type}


class WorkflowRepository:
    @staticmethod
    def definitions(db: Session) -> list[WorkflowDefinition]:
        return list(db.scalars(select(WorkflowDefinition).order_by(WorkflowDefinition.code, WorkflowDefinition.version.desc())))

    @staticmethod
    def definition(db: Session, code: str) -> WorkflowDefinition | None:
        return db.scalar(select(WorkflowDefinition).where(WorkflowDefinition.code == code).order_by(WorkflowDefinition.version.desc()).limit(1))

    @staticmethod
    def instances(db: Session, *, status: str | None, definition: str | None, limit: int, offset: int):
        stmt = select(WorkflowInstance)
        if status:
            stmt = stmt.where(WorkflowInstance.status == status)
        if definition:
            stmt = stmt.join(WorkflowDefinition).where(WorkflowDefinition.code == definition)
        return paginate(db, stmt, limit=limit, offset=offset, order_by=WorkflowInstance.updated_at.desc())

    @staticmethod
    def instance(db: Session, instance_id: uuid.UUID) -> WorkflowInstance | None:
        return db.get(WorkflowInstance, instance_id)

    @staticmethod
    def application_numbers(db: Session, app_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not app_ids:
            return {}
        return {i: n for i, n in db.execute(select(Application.id, Application.application_number).where(Application.id.in_(app_ids)))}


class ConnectorRepository:
    @staticmethod
    def calls(db: Session, connector_id: uuid.UUID, limit: int, offset: int):
        stmt = select(ConnectorCall).where(ConnectorCall.connector_id == connector_id)
        return paginate(db, stmt, limit=limit, offset=offset, order_by=ConnectorCall.created_at.desc())

    @staticmethod
    def by_key(db: Session, key: str) -> Connector | None:
        return db.scalar(select(Connector).where(Connector.key == key))


class ConsentRepository:
    @staticmethod
    def all(db: Session, *, status: str | None, limit: int, offset: int):
        stmt = select(Consent)
        if status:
            stmt = stmt.where(Consent.status == status)
        return paginate(db, stmt, limit=limit, offset=offset, order_by=Consent.granted_at.desc())
