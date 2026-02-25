import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")


class SignUpRequest(BaseModel):
    email: str = Field(..., description="User email (unique, case-insensitive)")
    password: str = Field(..., min_length=8, description="User password (min 8 chars)")
    role: str = Field(..., description="Initial role: admin/staff/resident")


class LoginRequest(BaseModel):
    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password")


class UserMeResponse(BaseModel):
    id: uuid.UUID = Field(..., description="User ID")
    email: str = Field(..., description="Email")
    role: str = Field(..., description="Role: admin/staff/resident")
    is_active: bool = Field(..., description="Whether user is active")


class UnitRef(BaseModel):
    id: uuid.UUID = Field(..., description="Unit ID")
    building: Optional[str] = Field(None, description="Building name/identifier")
    unit_number: str = Field(..., description="Unit number")
    floor: Optional[str] = Field(None, description="Floor")


class PrivacySettings(BaseModel):
    show_in_directory: bool = Field(..., description="Whether profile is visible in directory")
    show_unit: bool = Field(..., description="Whether unit is visible to other users in directory")
    show_phone: bool = Field(..., description="Whether phone is visible to other users in directory")
    show_email: bool = Field(..., description="Whether secondary email is visible to other users in directory")
    show_photo: bool = Field(..., description="Whether photo URL is visible to other users in directory")
    allow_contact_requests: bool = Field(..., description="Whether others can request contact with this user")


class ResidentProfileBase(BaseModel):
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    preferred_name: Optional[str] = Field(None, description="Preferred name")
    phone: Optional[str] = Field(None, description="Phone (may be private)")
    email_secondary: Optional[str] = Field(None, description="Secondary email (may be private)")
    bio: Optional[str] = Field(None, description="Short bio")

    unit_id: Optional[uuid.UUID] = Field(None, description="Unit ID")
    move_in_date: Optional[date] = Field(None, description="Move-in date")
    move_out_date: Optional[date] = Field(None, description="Move-out date")
    is_resident: bool = Field(default=True, description="Is resident (vs staff profile)")

    photo_url: Optional[str] = Field(None, description="Photo URL (may be private)")


class ResidentProfileCreate(ResidentProfileBase):
    privacy: PrivacySettings = Field(..., description="Initial privacy settings")


class ResidentProfileUpdate(BaseModel):
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    preferred_name: Optional[str] = Field(None, description="Preferred name")
    phone: Optional[str] = Field(None, description="Phone")
    email_secondary: Optional[str] = Field(None, description="Secondary email")
    bio: Optional[str] = Field(None, description="Bio")

    unit_id: Optional[uuid.UUID] = Field(None, description="Unit ID")
    move_in_date: Optional[date] = Field(None, description="Move-in date")
    move_out_date: Optional[date] = Field(None, description="Move-out date")
    is_resident: Optional[bool] = Field(None, description="Is resident")
    photo_url: Optional[str] = Field(None, description="Photo URL")

    privacy: Optional[PrivacySettings] = Field(None, description="Privacy settings update")


class ResidentProfileResponse(BaseModel):
    id: uuid.UUID = Field(..., description="Profile ID")
    user_id: uuid.UUID = Field(..., description="User ID")

    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    preferred_name: Optional[str] = Field(None, description="Preferred name")
    bio: Optional[str] = Field(None, description="Bio")

    # Potentially redacted depending on privacy + viewer
    phone: Optional[str] = Field(None, description="Phone (may be redacted)")
    email_secondary: Optional[str] = Field(None, description="Secondary email (may be redacted)")
    photo_url: Optional[str] = Field(None, description="Photo URL (may be redacted)")
    unit: Optional[UnitRef] = Field(None, description="Unit reference (may be redacted)")

    is_resident: bool = Field(..., description="Is resident")
    is_profile_approved: bool = Field(..., description="Whether profile is approved")
    approved_at: Optional[datetime] = Field(None, description="Approval time")
    approved_by: Optional[uuid.UUID] = Field(None, description="Approver user ID")

    privacy: PrivacySettings = Field(..., description="Privacy settings")

    created_at: datetime = Field(..., description="Created timestamp")
    updated_at: datetime = Field(..., description="Updated timestamp")


class DirectorySearchResponse(BaseModel):
    results: list[ResidentProfileResponse] = Field(..., description="Directory results (privacy enforced)")
    total: int = Field(..., description="Total matching records (before pagination)")
    limit: int = Field(..., description="Limit")
    offset: int = Field(..., description="Offset")


class AnnouncementCreate(BaseModel):
    title: str = Field(..., description="Title")
    body: str = Field(..., description="Body")
    audience: str = Field(..., description="Audience: all/staff/residents")
    is_published: bool = Field(default=False, description="Publish immediately")


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(None, description="Title")
    body: Optional[str] = Field(None, description="Body")
    audience: Optional[str] = Field(None, description="Audience")
    is_published: Optional[bool] = Field(None, description="Publish/unpublish")


class AnnouncementResponse(BaseModel):
    id: uuid.UUID = Field(..., description="Announcement ID")
    title: str = Field(..., description="Title")
    body: str = Field(..., description="Body")
    audience: str = Field(..., description="Audience")
    is_published: bool = Field(..., description="Published")
    published_at: Optional[datetime] = Field(None, description="Published at")
    created_by: Optional[uuid.UUID] = Field(None, description="Created by user")
    created_at: datetime = Field(..., description="Created at")
    updated_at: datetime = Field(..., description="Updated at")


class AuditLogResponse(BaseModel):
    id: uuid.UUID = Field(..., description="Audit log ID")
    actor_user_id: Optional[uuid.UUID] = Field(None, description="Actor user ID (nullable)")
    action: str = Field(..., description="Action name")
    entity_type: Optional[str] = Field(None, description="Entity type")
    entity_id: Optional[uuid.UUID] = Field(None, description="Entity id")
    metadata: dict[str, Any] = Field(..., description="Metadata payload")
    created_at: datetime = Field(..., description="Created at")
