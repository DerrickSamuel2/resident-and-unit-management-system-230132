from typing import Annotated, Optional
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.api.core.auth import get_current_user, require_roles
from src.api.core.db import get_db
from src.api.models import AuditLog, AuthUser
from src.api.schemas import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get(
    "",
    response_model=list[AuditLogResponse],
    summary="List audit log entries",
    description="Admin/staff only. Filter by actor_user_id and paginate.",
    dependencies=[Depends(require_roles({"admin", "staff"}))],
)
def list_audit(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    actor_user_id: Optional[uuid.UUID] = Query(default=None, description="Filter by actor user id"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List audit records."""
    stmt = select(AuditLog)
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)

    rows = db.scalars(stmt.order_by(desc(AuditLog.created_at)).limit(limit).offset(offset)).all()
    return [
        AuditLogResponse(
            id=r.id,
            actor_user_id=r.actor_user_id,
            action=r.action,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            metadata=r.metadata,
            created_at=r.created_at,
        )
        for r in rows
    ]
