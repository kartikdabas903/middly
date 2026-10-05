"""Configurable eligibility rules engine.

Rule sets are JSON (see /workflow-engine/rules). All shipped rules are DEMO
rules for the hackathon and are NOT real government eligibility criteria.

Supported operators:
    equals        field == value
    in / not_in   field in values
    age_between   age (from a date field) within [min, max]
    min_level     ordered level (qualification) >= min
    exists        field is present
    gte / lte     numeric comparison
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Callable

from app.integration.normalize import level_rank


@dataclass
class RuleOutcome:
    id: str
    passed: bool
    description: str
    reason: str
    actual: Any = None


@dataclass
class EligibilityResult:
    eligible: bool
    ruleset: str
    demo: bool
    passed_rules: list[str] = field(default_factory=list)
    failed_rules: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    outcomes: list[RuleOutcome] = field(default_factory=list)
    evaluated_on: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["outcomes"] = [asdict(o) for o in self.outcomes]
        return data


def _get(profile: dict[str, Any], path: str) -> Any:
    cur: Any = profile
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _age(dob: Any, on: date) -> int | None:
    if dob in (None, ""):
        return None
    d = dob if isinstance(dob, date) else date.fromisoformat(str(dob))
    return on.year - d.year - ((on.month, on.day) < (d.month, d.day))


def _equals(rule, value, on):
    ok = value is not None and str(value).lower() == str(rule["value"]).lower()
    return ok, value


def _in(rule, value, on):
    return value in rule["values"], value


def _not_in(rule, value, on):
    return value is not None and value not in rule["values"], value


def _age_between(rule, value, on):
    age = _age(value, on)
    return age is not None and rule["min"] <= age <= rule["max"], age


def _min_level(rule, value, on):
    return level_rank(value) >= level_rank(rule["min"]) and value is not None, value


def _exists(rule, value, on):
    return value not in (None, "", []), value


def _gte(rule, value, on):
    return value is not None and float(value) >= float(rule["value"]), value


def _lte(rule, value, on):
    return value is not None and float(value) <= float(rule["value"]), value


OPERATORS: dict[str, Callable[[dict, Any, date], tuple[bool, Any]]] = {
    "equals": _equals,
    "in": _in,
    "not_in": _not_in,
    "age_between": _age_between,
    "min_level": _min_level,
    "exists": _exists,
    "gte": _gte,
    "lte": _lte,
}


def evaluate(ruleset: dict[str, Any], profile: dict[str, Any], on: date | None = None) -> EligibilityResult:
    on = on or date.today()
    result = EligibilityResult(
        eligible=True,
        ruleset=ruleset.get("code", "UNNAMED"),
        demo=bool(ruleset.get("demo", True)),
        evaluated_on=on.isoformat(),
    )
    for rule in ruleset.get("rules", []):
        op = OPERATORS.get(rule["operator"])
        if op is None:
            raise ValueError(f"Unknown eligibility operator {rule['operator']!r}")
        value = _get(profile, rule["field"])
        try:
            passed, actual = op(rule, value, on)
        except (TypeError, ValueError):
            passed, actual = False, value
        outcome = RuleOutcome(
            id=rule["id"],
            passed=bool(passed),
            description=rule.get("description", rule["id"]),
            reason=rule.get("pass_message" if passed else "fail_message", ""),
            actual=actual,
        )
        result.outcomes.append(outcome)
        if passed:
            result.passed_rules.append(rule["id"])
        else:
            result.failed_rules.append(rule["id"])
            result.reasons.append(outcome.reason or f"{rule['id']} not satisfied")
    result.eligible = not result.failed_rules
    return result
