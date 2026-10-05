from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import Application, Service, WorkflowInstance, WorkflowStep


@dataclass
class StepOutcome:
    """What a step handler decided.

    COMPLETED -> move to the next step
    WAIT      -> pause the instance (consent, source outage, officer, citizen, event, external system)
    DECIDED   -> final decision reached early (e.g. auto-reject on eligibility)
    """

    kind: Literal["COMPLETED", "WAIT", "DECIDED"]
    output: dict[str, Any] = field(default_factory=dict)
    wait_status: str | None = None
    app_status: str | None = None
    decision: str | None = None
    reason: str | None = None
    error: str | None = None
    note: str | None = None

    @classmethod
    def completed(cls, output: dict[str, Any] | None = None, app_status: str | None = None, note: str | None = None) -> "StepOutcome":
        return cls("COMPLETED", output or {}, app_status=app_status, note=note)

    @classmethod
    def wait(cls, wait_status: str, *, app_status: str | None = None, output: dict[str, Any] | None = None, error: str | None = None, note: str | None = None) -> "StepOutcome":
        return cls("WAIT", output or {}, wait_status=wait_status, app_status=app_status, error=error, note=note)

    @classmethod
    def decided(cls, decision: str, reason: str, output: dict[str, Any] | None = None) -> "StepOutcome":
        return cls("DECIDED", output or {}, decision=decision, reason=reason)


@dataclass
class StepContext:
    db: "Session"
    instance: "WorkflowInstance"
    step: "WorkflowStep"
    step_def: dict[str, Any]
    application: "Application"
    service: "Service"

    def outputs_of(self, step_type: str) -> list[dict[str, Any]]:
        return [s.output for s in self.instance.steps if s.step_type == step_type and s.status == "COMPLETED"]


class StepHandler(Protocol):
    def execute(self, ctx: StepContext) -> StepOutcome: ...
