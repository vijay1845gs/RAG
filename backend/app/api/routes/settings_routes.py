"""
Settings routes — persistent, per-user AI workspace configuration.

Endpoints:
  GET  /settings/{user_id}         → fetch (auto-create defaults if none)
  PATCH /settings/{user_id}        → partial update
  POST  /settings/{user_id}/reset  → restore factory defaults

All writes go through the service-role admin client (_sb_write).
All reads use the anon client (_sb_read) with .eq("user_id", user_id).
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, Field

from app.db.supabase import get_supabase_client as get_anon_client
from app.db.supabase import get_supabase_admin_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["Settings"])


# ─────────────────────────────────────────────────────────────
# Defaults (single source of truth)
# ─────────────────────────────────────────────────────────────

DEFAULT_SETTINGS = {
    "default_collection": "default",
    "top_k": 5,
    "model_name": "qwen2.5:3b",
    "backend_url": "http://localhost:8000",
    "theme": "dark",
    "default_collection_id": None,
    "preferred_model": "gemini",
    "temperature": 0.3,
    "max_context_chunks": 5,
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "auto_scroll": True,
    "show_sources": True,
    "save_chat_history": True,
    "default_upload_collection": None,
    "rag_mode": "balanced",
    "response_style": "professional",
}


# ─────────────────────────────────────────────────────────────
# Supabase helpers (identical pattern to other routes)
# ─────────────────────────────────────────────────────────────

def _sb_read():
    """Return anon client for reads (respects RLS)."""
    sb = get_anon_client()
    if sb is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase client is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY.",
        )
    return sb


def _sb_write():
    """Return service-role client for writes (bypasses RLS)."""
    sb = get_supabase_admin_client()
    if sb is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase admin client is not configured. Set SUPABASE_SERVICE_ROLE_KEY.",
        )
    return sb


# ─────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    """Partial update payload — all fields optional. Must match actual database columns."""

    default_collection: Optional[str] = Field(default=None)
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    model_name: Optional[str] = Field(default=None)
    backend_url: Optional[str] = Field(default=None)
    theme: Optional[str] = Field(default=None)
    default_collection_id: Optional[str] = Field(default=None)
    preferred_model: Optional[str] = Field(default=None)
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    max_context_chunks: Optional[int] = Field(default=None, ge=1, le=20)
    chunk_size: Optional[int] = Field(default=None, ge=200, le=4000)
    chunk_overlap: Optional[int] = Field(default=None, ge=0)
    auto_scroll: Optional[bool] = Field(default=None)
    show_sources: Optional[bool] = Field(default=None)
    save_chat_history: Optional[bool] = Field(default=None)
    default_upload_collection: Optional[str] = Field(default=None)
    rag_mode: Optional[str] = Field(default=None)
    response_style: Optional[str] = Field(default=None)

    model_config = {"extra": "ignore"}


# ─────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────

def _fetch_settings_row(user_id: str) -> Optional[dict]:
    """Return existing settings row or None."""
    sb = _sb_read()
    res = (
        sb.table("settings")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def _create_default_settings(user_id: str) -> dict:
    """Insert a default settings row and return it."""
    sb = _sb_write()
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "id": str(uuid4()),
        "user_id": user_id,
        **DEFAULT_SETTINGS,
        "created_at": now,
        "updated_at": now,
    }
    res = sb.table("settings").insert(payload).execute()
    return res.data[0] if res.data else payload


# ─────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────

@router.get("/{user_id}", response_model=dict)
async def get_settings(user_id: str):
    """
    Fetch user settings. Auto-creates a default row if none exists.
    Never returns null.
    """
    row = _fetch_settings_row(user_id)
    if row is None:
        logger.info("No settings found for user_id=%s — creating defaults.", user_id)
        row = _create_default_settings(user_id)
    return row


@router.patch("/{user_id}", response_model=dict)
async def update_settings(user_id: str, body: SettingsUpdate = Body(...)):
    """
    Partial update — only supplied fields are modified.
    Auto-creates default row if the user has no settings yet.
    """
    # Ensure row exists
    existing = _fetch_settings_row(user_id)
    if existing is None:
        logger.info("No settings for user_id=%s on PATCH — creating defaults first.", user_id)
        _create_default_settings(user_id)

    # Build patch dict from explicitly supplied fields. Nullable fields need to
    # keep None so the UI can clear default collection selections.
    patch = body.model_dump(exclude_unset=True)
    nullable_fields = {"default_collection_id", "default_upload_collection"}
    patch = {
        k: v
        for k, v in patch.items()
        if v is not None or k in nullable_fields
    }
    if not patch:
        # Nothing to update; just return current settings
        return _fetch_settings_row(user_id)

    patch["updated_at"] = datetime.now(timezone.utc).isoformat()

    sb = _sb_write()
    try:
        res = (
            sb.table("settings")
            .update(patch)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        logger.exception("Failed to update settings for user_id=%s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {exc}",
        ) from exc

    return res.data[0] if res.data else _fetch_settings_row(user_id)


@router.post("/{user_id}/reset", response_model=dict)
async def reset_settings(user_id: str):
    """
    Restore factory defaults for the user.
    Creates the row if it doesn't exist.
    """
    existing = _fetch_settings_row(user_id)
    now = datetime.now(timezone.utc).isoformat()

    sb = _sb_write()
    try:
        if existing is None:
            # Insert fresh row
            payload = {
                "id": str(uuid4()),
                "user_id": user_id,
                **DEFAULT_SETTINGS,
                "created_at": now,
                "updated_at": now,
            }
            res = sb.table("settings").insert(payload).execute()
        else:
            # Overwrite to defaults
            reset_payload = {**DEFAULT_SETTINGS, "updated_at": now}
            res = (
                sb.table("settings")
                .update(reset_payload)
                .eq("user_id", user_id)
                .execute()
            )
    except Exception as exc:
        logger.exception("Failed to reset settings for user_id=%s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset settings: {exc}",
        ) from exc

    return res.data[0] if res.data else _fetch_settings_row(user_id)


__all__ = ["router"]
