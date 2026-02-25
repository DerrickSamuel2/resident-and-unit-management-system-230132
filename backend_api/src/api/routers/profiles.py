import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from src.api.core.audit import audit_log
from src.api.core.auth import get_current_user, require_roles
from src.api.core.db import get_db
from src.api.core.privacy import redact_profile_for_viewer
from src.api.models import AuthUser, ProfilePrivacySettings, ResidentProfile, Unit
from src.api.schemas import DirectorySearchResponse, ResidentProfileCreate, ResidentProfileResponse, ResidentProfileUpdate

router = APIRouter(prefix="/profiles", tags=["Profiles"])


def _get_profile_or_404(db: Session, profile_id: uuid.UUID) -> ResidentProfile:
    profile = db.scalar(
        select(ResidentProfile)
        .options(joinedload(ResidentProfile.privacy), joinedload(ResidentProfile.unit))
        .where(ResidentProfile.id == profile_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    if not profile.privacy:
        raise HTTPException(status_code=500, detail="Profile missing privacy settings")
    return profile


@router.post(
    "",
    response_model=ResidentProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a resident profile for a user",
    description="Creates a resident profile + privacy settings. Admin/staff can create for any user via user_id query param. Residents create only for themselves.",
)
def create_profile(
    payload: ResidentProfileCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    user_id: Optional[uuid.UUID] = Query(default=None, description="Target user_id (admin/staff only)"),
):
    """Create a profile. Residents can only create their own profile."""
    target_user_id = user_id or current_user.id
    if current_user.role == "resident" and target_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Residents can only create their own profile")

    # Ensure user exists
    target_user = db.scalar(select(AuthUser).where(AuthUser.id == target_user_id))
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = db.scalar(select(ResidentProfile).where(ResidentProfile.user_id == target_user_id))
    if existing:
        raise HTTPException(status_code=409, detail="Profile already exists for user")

    # Validate unit if provided
    unit = None
    if payload.unit_id:
        unit = db.scalar(select(Unit).where(Unit.id == payload.unit_id))
        if not unit:
            raise HTTPException(status_code=400, detail="Invalid unit_id")

    profile = ResidentProfile(
        id=uuid.uuid4(),
        user_id=target_user_id,
        unit_id=payload.unit_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        preferred_name=payload.preferred_name,
        phone=payload.phone,
        email_secondary=payload.email_secondary,
        bio=payload.bio,
        photo_url=payload.photo_url,
        move_in_date=payload.move_in_date,
        move_out_date=payload.move_out_date,
        is_resident=payload.is_resident,
        is_profile_approved=(current_user.role in {"admin", "staff"}),  # staff/admin auto-approve
        approved_at=(datetime.now(timezone.utc) if current_user.role in {"admin", "staff"} else None),
        approved_by=(current_user.id if current_user.role in {"admin", "staff"} else None),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    privacy = ProfilePrivacySettings(
        profile_id=profile.id,
        show_in_directory=payload.privacy.show_in_directory,
        show_unit=payload.privacy.show_unit,
        show_phone=payload.privacy.show_phone,
        show_email=payload.privacy.show_email,
        show_photo=payload.privacy.show_photo,
        allow_contact_requests=payload.privacy.allow_contact_requests,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(profile)
    db.add(privacy)

    audit_log(
        db,
        actor_user_id=current_user.id,
        action="profiles.create",
        entity_type="resident_profiles",
        entity_id=profile.id,
        metadata={"target_user_id": str(target_user_id)},
    )

    db.commit()

    created = _get_profile_or_404(db, profile.id)
    return ResidentProfileResponse.model_validate(redact_profile_for_viewer(viewer=current_user, profile=created))


@router.get(
    "/{profile_id}",
    response_model=ResidentProfileResponse,
    summary="Get a profile by id (privacy enforced)",
    description="Returns a profile with privacy enforcement. Owners and staff/admin see all fields.",
)
def get_profile(
    profile_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
):
    """Get a single profile with privacy enforcement."""
    profile = _get_profile_or_404(db, profile_id)

    # If not privileged and profile hidden from directory, block non-owner access
    if current_user.role == "resident" and current_user.id != profile.user_id and not profile.privacy.show_in_directory:
        raise HTTPException(status_code=404, detail="Profile not found")

    return ResidentProfileResponse.model_validate(redact_profile_for_viewer(viewer=current_user, profile=profile))


@router.patch(
    "/{profile_id}",
    response_model=ResidentProfileResponse,
    summary="Update a profile (privacy settings included)",
    description="Owners can update their profile; admin/staff can update any profile. Resident updates require re-approval.",
)
def update_profile(
    profile_id: uuid.UUID,
    payload: ResidentProfileUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
):
    """Update profile fields and privacy."""
    profile = _get_profile_or_404(db, profile_id)

    if current_user.role == "resident" and current_user.id != profile.user_id:
        raise HTTPException(status_code=403, detail="Cannot update other users' profiles")

    # Apply updates
    for field in ["first_name", "last_name", "preferred_name", "phone", "email_secondary", "bio", "unit_id", "move_in_date", "move_out_date", "is_resident", "photo_url"]:
        val = getattr(payload, field)
        if val is not None:
            setattr(profile, field, val)

    if payload.privacy is not None:
        profile.privacy.show_in_directory = payload.privacy.show_in_directory
        profile.privacy.show_unit = payload.privacy.show_unit
        profile.privacy.show_phone = payload.privacy.show_phone
        profile.privacy.show_email = payload.privacy.show_email
        profile.privacy.show_photo = payload.privacy.show_photo
        profile.privacy.allow_contact_requests = payload.privacy.allow_contact_requests

    # If resident updates their profile, require re-approval
    if current_user.role == "resident":
        profile.is_profile_approved = False
        profile.approved_at = None
        profile.approved_by = None

    profile.updated_at = datetime.now(timezone.utc)

    audit_log(
        db,
        actor_user_id=current_user.id,
        action="profiles.update",
        entity_type="resident_profiles",
        entity_id=profile.id,
        metadata={"reapproval_required": current_user.role == "resident"},
    )

    db.commit()
    updated = _get_profile_or_404(db, profile.id)
    return ResidentProfileResponse.model_validate(redact_profile_for_viewer(viewer=current_user, profile=updated))


@router.post(
    "/{profile_id}/approve",
    response_model=ResidentProfileResponse,
    summary="Approve a resident profile",
    description="Admin/staff can approve a profile to make it visible in the directory (subject to privacy settings).",
    dependencies=[Depends(require_roles({"admin", "staff"}))],
)
def approve_profile(
    profile_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
):
    """Approve profile."""
    profile = _get_profile_or_404(db, profile_id)
    profile.is_profile_approved = True
    profile.approved_at = datetime.now(timezone.utc)
    profile.approved_by = current_user.id
    profile.updated_at = datetime.now(timezone.utc)

    audit_log(db, actor_user_id=current_user.id, action="profiles.approve", entity_type="resident_profiles", entity_id=profile.id, metadata={})
    db.commit()

    approved = _get_profile_or_404(db, profile.id)
    return ResidentProfileResponse.model_validate(redact_profile_for_viewer(viewer=current_user, profile=approved))


@router.post(
    "/{profile_id}/decline",
    response_model=ResidentProfileResponse,
    summary="Decline (unapprove) a resident profile",
    description="Admin/staff can mark a profile as not approved.",
    dependencies=[Depends(require_roles({"admin", "staff"}))],
)
def decline_profile(
    profile_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
):
    """Decline/unapprove profile."""
    profile = _get_profile_or_404(db, profile_id)
    profile.is_profile_approved = False
    profile.approved_at = None
    profile.approved_by = None
    profile.updated_at = datetime.now(timezone.utc)

    audit_log(db, actor_user_id=current_user.id, action="profiles.decline", entity_type="resident_profiles", entity_id=profile.id, metadata={})
    db.commit()

    declined = _get_profile_or_404(db, profile.id)
    return ResidentProfileResponse.model_validate(redact_profile_for_viewer(viewer=current_user, profile=declined))


@router.get(
    "",
    response_model=DirectorySearchResponse,
    summary="Directory search and filtering (privacy enforced)",
    description=(
        "Search resident directory by name/unit. Returns only approved profiles. "
        "For residents: only profiles with show_in_directory=true are included. "
        "Admin/staff can see all approved profiles regardless of show_in_directory."
    ),
)
def directory_search(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    q: Optional[str] = Query(default=None, description="Name query (partial match)"),
    building: Optional[str] = Query(default=None, description="Filter by building"),
    unit_number: Optional[str] = Query(default=None, description="Filter by unit number"),
    is_resident: Optional[bool] = Query(default=None, description="Filter by resident flag"),
    limit: int = Query(default=20, ge=1, le=100, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Offset"),
):
    """Search directory with trigram-friendly ilike on search_name and optional unit filters."""
    stmt = (
        select(ResidentProfile)
        .options(joinedload(ResidentProfile.privacy), joinedload(ResidentProfile.unit))
        .where(ResidentProfile.is_profile_approved.is_(True))
    )

    if is_resident is not None:
        stmt = stmt.where(ResidentProfile.is_resident.is_(is_resident))

    if q:
        # Use search_name denormalized field for faster matching.
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(ResidentProfile.search_name.ilike(like), func.concat(ResidentProfile.first_name, " ", ResidentProfile.last_name).ilike(like)))

    if building or unit_number:
        stmt = stmt.join(Unit, ResidentProfile.unit_id == Unit.id, isouter=True)
        if building:
            stmt = stmt.where(Unit.building == building)
        if unit_number:
            stmt = stmt.where(Unit.unit_number == unit_number)

    # Privacy gating for residents: only show profiles that opted in.
    if current_user.role == "resident":
        stmt = stmt.join(ProfilePrivacySettings, ProfilePrivacySettings.profile_id == ResidentProfile.id).where(ProfilePrivacySettings.show_in_directory.is_(True))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(ResidentProfile.last_name.asc(), ResidentProfile.first_name.asc()).limit(limit).offset(offset)).all()

    results = [ResidentProfileResponse.model_validate(redact_profile_for_viewer(viewer=current_user, profile=p)) for p in rows]
    return DirectorySearchResponse(results=results, total=total, limit=limit, offset=offset)
