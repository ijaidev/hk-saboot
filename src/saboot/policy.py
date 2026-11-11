"""Policy book loading, clause lookup, and cap evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from .schema import SabootError, quantize_money


@dataclass(frozen=True)
class PolicyClause:
    id: str
    code: str
    title: str
    text: str
    source_url: str
    effective_from: date
    effective_to: date
    jurisdiction: str
    applies_to: tuple[str, ...]
    remedy: str
    cap_rule: dict[str, Any] | None

    def applies(
        self,
        claim_type: str,
        code: str,
        event_date: date,
        jurisdiction: str,
    ) -> bool:
        if claim_type not in self.applies_to:
            return False
        if code != "*" and self.code != "*" and code != self.code:
            return False
        if self.jurisdiction not in ("*", jurisdiction):
            return False
        return self.effective_from <= event_date <= self.effective_to

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "code": self.code,
            "title": self.title,
            "text": self.text,
            "source_url": self.source_url,
            "effective_from": self.effective_from.isoformat(),
            "effective_to": self.effective_to.isoformat(),
            "jurisdiction": self.jurisdiction,
            "applies_to": list(self.applies_to),
            "remedy": self.remedy,
            "cap_rule": self.cap_rule,
        }


@dataclass
class PolicyBook:
    id: str
    version: str
    platform: str
    jurisdiction: str
    currency: str
    effective_from: date
    effective_to: date
    synthetic: bool
    disclaimer: str
    clauses: list[PolicyClause]
    path: str = ""

    def __post_init__(self) -> None:
        self._by_id = {c.id: c for c in self.clauses}

    def clause(self, clause_id: str) -> PolicyClause | None:
        return self._by_id.get(clause_id)

    def find(
        self,
        claim_type: str,
        code: str,
        event_date: date | datetime,
        jurisdiction: str | None = None,
    ) -> PolicyClause | None:
        event_day = event_date.date() if isinstance(event_date, datetime) else event_date
        jurisdiction = jurisdiction or self.jurisdiction
        candidates = [
            clause
            for clause in self.clauses
            if clause.applies(claim_type, code, event_day, jurisdiction)
        ]
        if not candidates:
            return None

        def sort_key(clause: PolicyClause) -> tuple[int, int, int, str]:
            exact_code = 0 if clause.code == code else 1
            exact_jurisdiction = 0 if clause.jurisdiction == jurisdiction else 1
            # Prefer the most recent effective clause.
            recency = -clause.effective_from.toordinal()
            return (exact_code, exact_jurisdiction, recency, clause.id)

        return sorted(candidates, key=sort_key)[0]

    def evaluate_cap(self, clause: PolicyClause, order_total_pay: Decimal) -> Decimal | None:
        if not clause.cap_rule:
            return None
        value = self._eval_rule(clause.cap_rule, order_total_pay)
        if value is None:
            return None
        return quantize_money(value)

    def _eval_rule(self, rule: dict[str, Any], order_total_pay: Decimal) -> Decimal | None:
        rule_type = rule.get("type")
        if rule_type == "fixed":
            return Decimal(str(rule.get("value", 0)))
        if rule_type == "percent_of_order_pay":
            return order_total_pay * Decimal(str(rule.get("value", 0)))
        values = rule.get("values", [])
        if rule_type in ("max_of", "min_of"):
            evaluated = [self._eval_rule(v, order_total_pay) for v in values]
            evaluated = [v for v in evaluated if v is not None]
            if not evaluated:
                return None
            return max(evaluated) if rule_type == "max_of" else min(evaluated)
        raise SabootError(f"Unsupported cap_rule type: {rule_type!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "platform": self.platform,
            "jurisdiction": self.jurisdiction,
            "currency": self.currency,
            "effective_from": self.effective_from.isoformat(),
            "effective_to": self.effective_to.isoformat(),
            "synthetic": self.synthetic,
            "disclaimer": self.disclaimer,
            "clauses": [c.to_dict() for c in self.clauses],
        }

    @classmethod
    def load(cls, path: str | Path) -> "PolicyBook":
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise SabootError(f"Policy file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise SabootError(f"Policy file is not valid JSON: {path}: {exc}") from exc

        clauses: list[PolicyClause] = []
        for raw in data.get("clauses", []):
            source_url = str(raw.get("source_url", ""))
            if not source_url.startswith(("https://", "http://")):
                raise SabootError(
                    f"Policy clause {raw.get('id')} must have an http(s) source_url"
                )
            clauses.append(
                PolicyClause(
                    id=str(raw["id"]),
                    code=str(raw.get("code", "*")),
                    title=str(raw.get("title", "")),
                    text=str(raw.get("text", "")),
                    source_url=source_url,
                    effective_from=date.fromisoformat(str(raw["effective_from"])),
                    effective_to=date.fromisoformat(str(raw["effective_to"])),
                    jurisdiction=str(raw.get("jurisdiction", "*")),
                    applies_to=tuple(str(x) for x in raw.get("applies_to", [])),
                    remedy=str(raw.get("remedy", "")),
                    cap_rule=raw.get("cap_rule"),
                )
            )

        book = cls(
            id=str(data["id"]),
            version=str(data["version"]),
            platform=str(data["platform"]),
            jurisdiction=str(data.get("jurisdiction", "*")),
            currency=str(data.get("currency", "INR")),
            effective_from=date.fromisoformat(str(data["effective_from"])),
            effective_to=date.fromisoformat(str(data["effective_to"])),
            synthetic=bool(data.get("synthetic", False)),
            disclaimer=str(data.get("disclaimer", "")),
            clauses=clauses,
            path=str(path),
        )
        return book
