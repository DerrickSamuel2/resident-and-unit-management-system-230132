import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.api.core.audit import audit_log
from src.api.core.auth import get_current_user, require_roles
from src.api.core.db import get_db
from src.api.models import Announcement, AuthUser
from src.api.schemas import AnnouncementCreate, AnnouncementResponse, AnnouncementUpdate

router = APIRouter(prefix="/announcements", tags=["Announcements"])


def _get_or_404(db: Session, announcement_id: uuid.UUID) -> Announcement:
    a = db.scalar(select(Announcement).where(Announcement.id == announcement_id))
    if not a:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return a


@router.post(
    "",
    response_model=AnnouncementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an announcement",
    description="Admin/staff can create announcements. Can be saved as draft or published immediately.",
    dependencies=[Depends(require_roles({"admin", "staff"}))],
)
def create_announcement(
    payload: AnnouncementCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
):
    """Create announcement."""
    if payload.audience not in {"all", "staff", "residents"}:
        raise HTTPException(status_code=400, detail="Invalid audience")

    now = datetime.now(timezone.utc)
    ann = Announcement(
        id=uuid.uuid4(),
        title=payload.title,
        body=payload.body,
        audience=payload.audience,
        is_published=payload.is_published,
        published_at=(now if payload.is_published else None),
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(ann)
    audit_log(db, actor_user_id=current_user.id, action="announcements.create", entity_type="announcements", entity_id=ann.id, metadata={"is_published": payload.is_published})
    db.commit()
    db.refresh(ann)
    return AnnouncementResponse.model_validate(ann.__dict__)


@router.get(
    "",
    response_model=list[AnnouncementResponse],
    summary="List announcements",
    description="Residents see published announcements for their audience. Staff/admin can see drafts too (optional via include_drafts).",
)
def list_announcements(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    include_drafts: bool = Query(default=False, description="Include unpublished announcements (staff/admin only)"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List announcements filtered by audience and publication state."""
    stmt = select(Announcement)

    if current_user.role in {"admin", "staff"} and include_drafts:
        pass
    else:
        stmt = stmt.where(Announcement.is_published.is_(True))

    if current_user.role == "resident":
        stmt = stmt.where(Announcement.audience.in_(["all", "residents"]))
    elif current_user.role in {"admin", "staff"}:
        # staff/admin can see all audiences
        pass
    else:
        stmt = stmt.where(Announcement.audience == "all")

    rows = db.scalars(stmt.order_by(desc(Announcement.published_at), desc(Announcement.created_at)).limit(limit).offset(offset)).all()
    return [AnnouncementResponse.model_validate(r.__dict__) for r in rows]


@router.get(
    "/{announcement_id}",
    response_model=AnnouncementResponse,
    summary="Get announcement by id",
    description="Residents can access only published announcements visible to them.",
)
def get_announcement(
    announcement_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
):
    """Get announcement with access control."""
    ann = _get_or_404(db, announcement_id)

    if current_user.role == "resident":
        if not ann.is_published:
            raise HTTPException(status_code=404, detail="Announcement not found")
        if ann.audience not in {"all", "residents"}:
            raise HTTPException(status_code=404, detail="Announcement not found")

    return AnnouncementResponse.model_validate(ann.__dict__)


@router.patch(
    "/{announcement_id}",
    response_model=AnnouncementResponse,
    summary="Update an announcement",
    description="Admin/staff can update title/body/audience and publish/unpublish.",
    dependencies=[Depends(require_roles({"admin", "staff"}))],
)
def update_announcement(
    announcement_id: uuid.UUID,
    payload: AnnouncementUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
):
    """Update announcement."""
    ann = _get_or_404(db, announcement_id)
    now = datetime.now(timezone.utc)

    if payload.title is not None:
        ann.title = payload.title
    if payload.body is not None:
        ann.body = payload.body
    if payload.audience is not None:
        if payload.audience not in {"all", "staff", "residents"}:
            raise HTTPException(status_code=400, detail="Invalid audience")
        ann.audience = payload.audience

    if payload.is_published is not None:
        ann.is_published = payload.is_published
        ann.published_at = (now if payload.is_published else None)

    ann.updated_at = now

    audit_log(db, actor_user_id=current_user.id, action="announcements.update", entity_type="announcements", entity_id=ann.id, metadata={})
    db.commit()
    db.refresh(ann)
    return AnnouncementResponse.model_validate(ann.__dict__)


@router.delete(
    "/{announcement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an announcement",
    description="Admin/staff can delete an announcement.",
    dependencies=[Depends(require_roles({"admin", "staff"}))],
)
def delete_announcement(
    announcement_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
):
    """Delete announcement."""
    ann = _get_or_404(db, announcement_id)
    audit_log(db, actor_user_id=current_user.id, action="announcements.delete", entity_type="announcements", entity_id=ann.id, metadata={})
    db.delete(ann)
    db.commit()
    return None
