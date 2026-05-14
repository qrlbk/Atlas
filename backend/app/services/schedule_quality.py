"""Aggregate schedule quality (penalty) from validation issues."""

from __future__ import annotations

from collections import defaultdict

from app.schemas.validation import ValidationIssue


def score_validation_issues(issues: list[ValidationIssue]) -> dict:
    """Sum penalty weights and group by issue code and severity."""
    total_penalty = sum(i.weight for i in issues)
    breakdown_by_code: dict[str, float] = defaultdict(float)
    by_severity: dict[str, float] = defaultdict(float)
    for issue in issues:
        breakdown_by_code[issue.issue_code] += issue.weight
        by_severity[issue.severity] += issue.weight
    return {
        "total_penalty": total_penalty,
        "breakdown_by_code": dict(breakdown_by_code),
        "by_severity": dict(by_severity),
        "error_count": sum(1 for i in issues if i.severity == "error"),
        "warning_count": sum(1 for i in issues if i.severity == "warning"),
    }
