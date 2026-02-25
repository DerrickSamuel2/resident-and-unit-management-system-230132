import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.core.audit import audit_log
from src.api.core.auth import create_access_token, get_current_user, hash_password, set_last_login, verify_password
from src.api.core.db import get_db
from src.api.models import AuthUser
from src.api.schemas import LoginRequest, SignUpRequest, TokenResponse, UserMeResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/signup",
    response_model=UserMeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (admin/staff/resident)",
    description="Creates a new user in auth_users. Intended for bootstrap/dev; production may restrict this.",
)
def signup(payload: SignUpRequest, db: Annotated[Session, Depends(get_db)]):
    """Create user with email/password and role."""
    role = payload.role.strip().lower()
    if role not in {"admin", "staff", "resident"}:
        raise HTTPException(status_code=400, detail="Invalid role")

    existing = db.scalar(select(AuthUser).where(AuthUser.email == payload.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")

    user = AuthUser(
        id=uuid.uuid4(),
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    audit_log(db, actor_user_id=user.id, action="auth.signup", entity_type="auth_users", entity_id=user.id, metadata={"email": user.email, "role": user.role})
    db.commit()
    db.refresh(user)
    return UserMeResponse(id=user.id, email=user.email, role=user.role, is_active=user.is_active)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive JWT",
    description="Validates email/password and returns a JWT access token.",
)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]):
    """Authenticate user and return JWT."""
    user = db.scalar(select(AuthUser).where(AuthUser.email == payload.email))
    if not user or not user.password_hash:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    set_last_login(db, user.id)
    audit_log(db, actor_user_id=user.id, action="auth.login", entity_type="auth_users", entity_id=user.id, metadata={})
    db.commit()

    token = create_access_token(sub=str(user.id), role=user.role)
    return TokenResponse(access_token=token, token_type="bearer")


@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Get current user",
    description="Returns the authenticated user's identity and role.",
)
def me(user: Annotated[AuthUser, Depends(get_current_user)]):
    """Return current user."""
    return UserMeResponse(id=user.id, email=user.email, role=user.role, is_active=user.is_active)
