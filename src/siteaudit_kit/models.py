"""Stable report primitives; fingerprints deliberately exclude line numbers."""

from collections import Counter
from dataclasses import asdict, dataclass, field, replace
import hashlib
import json

SEVERITIES = {"info": 0, "warning": 1, "error": 2}


@dataclass(frozen=True)
class Rule:
    id: str
    category: str
    severity: str
    title: str
    fix: str
    reference: str


@dataclass(frozen=True)
class Finding:
    rule_id: str
    category: str
    severity: str
    title: str
    message: str
    fix: str
    reference: str
    source: str
    line: int
    evidence: str
    fingerprint: str
    is_new: bool = True

    @classmethod
    def from_rule(cls, rule: Rule, *, source: str, message: str,
                  line: int = 1, evidence: str = "document") -> "Finding":
        payload = json.dumps([rule.id, source, evidence], ensure_ascii=True)
        fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return cls(rule.id, rule.category, rule.severity, rule.title, message,
                   rule.fix, rule.reference, source, max(1, line), evidence, fingerprint)


@dataclass
class Report:
    source: str
    findings: list[Finding] = field(default_factory=list)
    checks_run: list[str] = field(default_factory=list)
    checks_skipped: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "source": self.source,
            "summary": {severity: sum(f.severity == severity for f in self.findings)
                        for severity in SEVERITIES},
            "new_findings": sum(f.is_new for f in self.findings),
            "checks_run": self.checks_run,
            "checks_skipped": self.checks_skipped,
            "findings": [asdict(f) for f in self.findings],
        }

    def baseline(self) -> dict:
        return {"schema_version": 1,
                "fingerprints": [f.fingerprint for f in self.findings]}

    def apply_baseline(self, payload: object) -> None:
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("baseline must be a schema_version 1 baseline or JSON report")
        fingerprints = payload.get("fingerprints")
        if fingerprints is None:
            items = payload.get("findings")
            if not isinstance(items, list) or not all(isinstance(f, dict) for f in items):
                raise ValueError("baseline is missing fingerprints or findings")
            fingerprints = [f.get("fingerprint") for f in items]
        if not isinstance(fingerprints, list) or not all(
            isinstance(f, str) and len(f) == 64 and all(c in "0123456789abcdef" for c in f)
            for f in fingerprints
        ):
            raise ValueError("baseline fingerprints must be lowercase SHA-256 hex strings")
        counts = Counter(fingerprints)
        updated = []
        for finding in self.findings:
            accepted = counts[finding.fingerprint] > 0
            if accepted:
                counts[finding.fingerprint] -= 1
            updated.append(replace(finding, is_new=not accepted))
        self.findings = updated

    def fails(self, severity: str = "error") -> bool:
        if severity == "none":
            return False
        if severity not in SEVERITIES:
            raise ValueError("unknown severity")
        return any(f.is_new and SEVERITIES[f.severity] >= SEVERITIES[severity]
                   for f in self.findings)
