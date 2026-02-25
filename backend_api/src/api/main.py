from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.core.config import get_settings
from src.api.routers import announcements_router, audit_router, auth_router, profiles_router

settings = get_settings()

openapi_tags = [
    {"name": "Auth", "description": "Authentication and identity endpoints."},
    {"name": "Profiles", "description": "Resident profile CRUD, directory search, and approvals."},
    {"name": "Announcements", "description": "Announcement creation and publication."},
    {"name": "Audit", "description": "Audit log access (admin/staff)."},
    {"name": "System", "description": "System/health endpoints."},
]

app = FastAPI(
    title=settings.app_name,
    description="Resident Directory App backend API providing authentication, RBAC, approvals, directory search, announcements, and audit logging.",
    version=settings.app_version,
    openapi_tags=openapi_tags,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.resolved_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(profiles_router)
app.include_router(announcements_router)
app.include_router(audit_router)


@app.get("/", tags=["System"], summary="Health check", description="Simple health check endpoint.")
def health_check():
    """Health check endpoint."""
    return {"message": "Healthy"}


@app.get(
    "/docs-help",
    tags=["System"],
    summary="API usage notes",
    description="Notes about authentication and common workflows.",
)
def docs_help():
    """Return basic API usage notes for developers."""
    return {
        "auth": {
            "login": {"path": "/auth/login", "token_type": "bearer", "use_header": "Authorization: Bearer <token>"},
            "me": {"path": "/auth/me"},
        },
        "workflows": {
            "profile_approval": "Residents creating/updating profiles require admin/staff approval via POST /profiles/{profile_id}/approve.",
            "directory_search": "GET /profiles?q=... returns privacy-enforced results. Residents only see profiles with show_in_directory=true.",
        },
    }
