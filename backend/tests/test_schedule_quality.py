from app.schemas.validation import ValidationIssue
from app.services.schedule_quality import score_validation_issues


def test_score_validation_issues_sums_weights():
    issues = [
        ValidationIssue(
            issue_code="A",
            severity="warning",
            message="m",
            entity_refs={},
            weight=10.0,
        ),
        ValidationIssue(
            issue_code="A",
            severity="warning",
            message="m2",
            entity_refs={},
            weight=5.0,
        ),
    ]
    out = score_validation_issues(issues)
    assert out["total_penalty"] == 15.0
    assert out["breakdown_by_code"]["A"] == 15.0
    assert out["warning_count"] == 2
