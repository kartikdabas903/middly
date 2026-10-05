"""Import every model so Alembic and the metadata see the full schema."""
from app.models.application import Application, ApplicationSequence, ApplicationStatusHistory
from app.models.audit import AuditLog
from app.models.citizen import Citizen
from app.models.connector import Connector, ConnectorCall, ConnectorHealth
from app.models.consent import Consent, ConsentAccessLog
from app.models.data_quality import DataQualityIssue
from app.models.department import Department, Service
from app.models.event import Event
from app.models.notification import Notification
from app.models.user import Role, User, user_roles
from app.models.workflow import WorkflowDefinition, WorkflowInstance, WorkflowStep

__all__ = [
    "Application",
    "ApplicationSequence",
    "ApplicationStatusHistory",
    "AuditLog",
    "Citizen",
    "Connector",
    "ConnectorCall",
    "ConnectorHealth",
    "Consent",
    "ConsentAccessLog",
    "DataQualityIssue",
    "Department",
    "Event",
    "Notification",
    "Role",
    "Service",
    "User",
    "WorkflowDefinition",
    "WorkflowInstance",
    "WorkflowStep",
    "user_roles",
]
