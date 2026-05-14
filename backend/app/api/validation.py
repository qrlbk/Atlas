from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import enforce_school_scope, get_current_user
from app.core.db import get_db
from app.models.entities import User
from app.i18n import localize_issue
from app.schemas.validation import ValidationRequest, ValidationResponse
from app.services.schedule_quality import score_validation_issues
from app.services.school_integrity import assert_schedule_payload_consistent
from app.services.validation_engine import validate_schedule


router = APIRouter(prefix="/validation", tags=["validation"])


@router.post("", response_model=ValidationResponse)
def validate(
    payload: ValidationRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ValidationResponse:
    enforce_school_scope(current_user, payload.school_id)
    if payload.candidate is not None:
        assert_schedule_payload_consistent(db, payload.candidate)
    issues = validate_schedule(db, payload.school_id, payload.candidate)
    locale = getattr(request.state, "locale", "en")
    for issue in issues:
        message, suggested_fix = localize_issue(issue.issue_code, locale, **(issue.message_params or {}))
        issue.message = message
        if suggested_fix:
            issue.suggested_fix = suggested_fix
    if any(i.severity == "error" for i in issues):
        status = "error"
    elif any(i.severity == "warning" for i in issues):
        status = "warning"
    else:
        status = "ok"
    return ValidationResponse(status=status, issues=issues, quality=score_validation_issues(issues))
