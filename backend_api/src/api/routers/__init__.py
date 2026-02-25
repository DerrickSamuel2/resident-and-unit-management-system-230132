from src.api.routers.announcements import router as announcements_router
from src.api.routers.audit import router as audit_router
from src.api.routers.auth import router as auth_router
from src.api.routers.profiles import router as profiles_router

__all__ = ["auth_router", "profiles_router", "announcements_router", "audit_router"]
