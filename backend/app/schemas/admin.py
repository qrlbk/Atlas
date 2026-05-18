from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminUserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    school_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminSchoolListItem(BaseModel):
    id: int
    name: str
    address: str
    plan: str
    trial_ends_at: str | None = None
    subscription_ends_at: str | None = None
    schedule_publish_state: str = "draft"
    created_at: str
    readiness_status: str = "unknown"
    readiness_checked_at: str | None = None
    last_event_at: str | None = None
    pro_access: bool = False
    manager_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class AdminSchoolListResponse(BaseModel):
    items: list[AdminSchoolListItem]
    total: int
    page: int
    page_size: int


class AdminUsageOut(BaseModel):
    metric: str
    period: str
    count: int


class AdminSnapshotOut(BaseModel):
    id: int
    label: str
    reason: str
    created_at: str
    item_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class AdminReadinessOut(BaseModel):
    status: str
    blockers: list[str] = []
    recommendations: list[str] = []
    summary: dict = Field(default_factory=dict)


class AdminSchoolDetail(BaseModel):
    school: AdminSchoolListItem
    readiness: AdminReadinessOut
    users: list[AdminUserOut]
    usage: list[AdminUsageOut]
    snapshots: list[AdminSnapshotOut]
    admin_notes: str | None = None
    manual_pro: bool = False


class AdminBillingPatch(BaseModel):
    status: str | None = None
    amount_kzt: int | None = None
    period_label: str | None = None
    paid_at: str | None = None
    notes: str | None = None


class AdminSchoolPatch(BaseModel):
    name: str | None = None
    address: str | None = None
    plan: str | None = None
    trial_ends_at: str | None = None
    subscription_ends_at: str | None = None
    admin_notes: str | None = None
    manual_pro: bool | None = None
    billing: AdminBillingPatch | None = None


class AdminSchoolCreate(BaseModel):
    name: str
    address: str
    manager_email: EmailStr
    manager_full_name: str
    trial_days: int = 14


class AdminSchoolCreateResponse(BaseModel):
    school_id: int
    manager_email: str
    manager_password: str


class AdminAttentionItem(BaseModel):
    school_id: int
    school_name: str
    reason: str
    plan: str
    readiness_status: str
    trial_ends_at: str | None = None
    last_event_at: str | None = None


class AdminDashboardOut(BaseModel):
    total_schools: int
    free_count: int
    pro_count: int
    trial_active_count: int
    readiness_red_count: int
    events_last_24h: int
    attention: list[AdminAttentionItem]


class AdminEventOut(BaseModel):
    id: int
    event_type: str
    created_at: str
    user_id: int | None = None
    payload: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminEventsPage(BaseModel):
    items: list[AdminEventOut]
    total: int
    page: int
    page_size: int


class AdminExtendTrialIn(BaseModel):
    days: int = 14


class AdminActivateProIn(BaseModel):
    until: str
    amount_kzt: int | None = None
    period_label: str | None = None
