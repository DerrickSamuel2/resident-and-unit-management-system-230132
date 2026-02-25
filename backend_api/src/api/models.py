import uuid
from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


class AppRole(str, Enum):
    admin = "admin"
    staff = "staff"
    resident = "resident"


class AnnouncementAudience(str, Enum):
    all = "all"
    staff = "staff"
    residents = "residents"


class AuthUser(Base):
    __tablename__ = "auth_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(CITEXT(), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(Text(), nullable=True)
    role: Mapped[str] = mapped_column(String(), index=True)  # enum in DB
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True)

    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["ResidentProfile"] = relationship(back_populates="user", uselist=False)


class Unit(Base):
    __tablename__ = "units"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    building: Mapped[str | None] = mapped_column(Text(), nullable=True)
    unit_number: Mapped[str] = mapped_column(Text(), nullable=False)
    floor: Mapped[str | None] = mapped_column(Text(), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    residents: Mapped[list["ResidentProfile"]] = relationship(back_populates="unit")


class ResidentProfile(Base):
    __tablename__ = "resident_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="CASCADE"), unique=True)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="SET NULL"), nullable=True)

    first_name: Mapped[str] = mapped_column(Text(), nullable=False)
    last_name: Mapped[str] = mapped_column(Text(), nullable=False)
    preferred_name: Mapped[str | None] = mapped_column(Text(), nullable=True)
    phone: Mapped[str | None] = mapped_column(Text(), nullable=True)
    email_secondary: Mapped[str | None] = mapped_column(CITEXT(), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text(), nullable=True)

    photo_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    photo_storage_key: Mapped[str | None] = mapped_column(Text(), nullable=True)
    photo_content_type: Mapped[str | None] = mapped_column(Text(), nullable=True)
    photo_file_size_bytes: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    photo_width: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    photo_height: Mapped[int | None] = mapped_column(Integer(), nullable=True)

    move_in_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    move_out_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    is_resident: Mapped[bool] = mapped_column(Boolean(), default=True)
    is_profile_approved: Mapped[bool] = mapped_column(Boolean(), default=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)

    search_name: Mapped[str | None] = mapped_column(Text(), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[AuthUser] = relationship(back_populates="profile")
    unit: Mapped[Unit | None] = relationship(back_populates="residents")
    privacy: Mapped["ProfilePrivacySettings"] = relationship(back_populates="profile", uselist=False)


class ProfilePrivacySettings(Base):
    __tablename__ = "profile_privacy_settings"

    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("resident_profiles.id", ondelete="CASCADE"), primary_key=True)

    show_in_directory: Mapped[bool] = mapped_column(Boolean(), default=True)
    show_unit: Mapped[bool] = mapped_column(Boolean(), default=True)
    show_phone: Mapped[bool] = mapped_column(Boolean(), default=False)
    show_email: Mapped[bool] = mapped_column(Boolean(), default=False)
    show_photo: Mapped[bool] = mapped_column(Boolean(), default=True)
    allow_contact_requests: Mapped[bool] = mapped_column(Boolean(), default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped[ResidentProfile] = relationship(back_populates="privacy")


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    title: Mapped[str] = mapped_column(Text(), nullable=False)
    body: Mapped[str] = mapped_column(Text(), nullable=False)
    audience: Mapped[str] = mapped_column(String(), nullable=False)  # enum in DB
    is_published: Mapped[bool] = mapped_column(Boolean(), default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(Text(), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(Text(), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata: Mapped[dict] = mapped_column(JSONB(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
