"""
Auth routes — Supabase-backed profiles and user management.

All endpoints read/write via the Supabase Postgres client
(through `app.db.supabase`), NOT through the local RAG tables.
"""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.db.supabase import get_supabase_client
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


# ─── Schemas ─────────────────────────────────────────────────────────

class ProfileCreate(BaseModel):
    user_id: str = Field(..., description="Supabase auth.users UUID")
    full_name: str | None = Field(None, max_length=200)


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(None, max_length=200)


class ProfileResponse(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    avatar_url: str | None = None
    created_at: str | None = None


# ─── Helpers ─────────────────────────────────────────────────────────

def _sb():
    client = get_supabase_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase client is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY in .env.",
        )
    return client


# ─── Endpoints ─────────────────────────────────────────────────────────

@router.get(
    "/profile/{user_id}",
    response_model=ProfileResponse,
    responses={404: {"description": "Profile not found"}},
)
async def get_profile(user_id: str) -> ProfileResponse:
    """Return a user's public profile row."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid user_id format")

    sb = _sb()
    if sb is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase client is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY in .env.",
        )
    res = (
        sb.table("profiles")
        .select("id, email, full_name, avatar_url, created_at")
        .eq("id", str(uid))
        .execute()
    )

    if not res.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    row = res.data[0]
    return ProfileResponse(
        id=str(row["id"]),
        email=row["email"],
        full_name=row.get("full_name"),
        avatar_url=row.get("avatar_url"),
        created_at=row.get("created_at"),
    )


@router.post("/profile", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(payload: ProfileCreate) -> ProfileResponse:
    """Create a profile entry (called after Supabase Auth sign-up)."""
    try:
        uid = uuid.UUID(payload.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid user_id format")

    sb = _sb()
    row = {"id": str(uid), "full_name": payload.full_name}
    res = sb.table("profiles").upsert(row, on_conflict="id").execute()
    data = (res.data or [{}])[0]
    return ProfileResponse(
        id=str(data.get("id", uid)),
        email="",
        full_name=data.get("full_name"),
        avatar_url=data.get("avatar_url"),
        created_at=data.get("created_at"),
    )


@router.patch("/profile/{user_id}", response_model=ProfileResponse)
async def update_profile(user_id: str, payload: ProfileUpdate) -> ProfileResponse:
    """Update a profile entry."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid user_id format")

    sb = _sb()
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")

    res = sb.table("profiles").update(updates).eq("id", str(uid)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Profile not found")

    row = res.data[0]
    return ProfileResponse(
        id=str(row["id"]),
        email=row.get("email", ""),
        full_name=row.get("full_name"),
        avatar_url=row.get("avatar_url"),
        created_at=row.get("created_at"),
    )


__all__ = ["router"]
