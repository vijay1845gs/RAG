"""
Chat history routes – canonical session identifier is chat_sessions.id (UUID PK).

chat_sessions:
- id (PK/UUID)
- user_id
- title
- created_at
- updated_at

chat_messages:
- id (PK/UUID)
- session_id (FK → chat_sessions.id)
- user_id
- question
- answer
- sources_json
- response_time
- created_at
"""

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

# anon-key client for reads (respects RLS)
from app.db.supabase import get_supabase_client as get_anon_client

# service-role client for writes
from app.db.supabase import get_supabase_admin_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat History"])


# ─────────────────────────────────────────────────────────────
# Supabase helpers
# ─────────────────────────────────────────────────────────────

def _sb_read():
    """Return anon client for reads."""
    sb = get_anon_client()

    if sb is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Supabase client is not configured. "
                "Set SUPABASE_URL and SUPABASE_ANON_KEY."
            ),
        )

    return sb


def _sb_write():
    """Return admin/service-role client for writes."""
    sb = get_supabase_admin_client()

    if sb is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Supabase admin client is not configured. "
                "Set SUPABASE_SERVICE_ROLE_KEY."
            ),
        )

    return sb


# ─────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────

class SaveMessageRequest(BaseModel):
    session_id: str
    question: str
    answer: str
    sources_json: Optional[Any] = None
    response_time: Optional[float] = None
    user_id: Optional[str] = None

    model_config = {"extra": "allow"}


# ─────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────

@router.get("/sessions", response_model=List[dict])
async def list_sessions(user_id: str):
    """List all sessions for a user."""

    sb = _sb_read()

    res = (
        sb.table("chat_sessions")
        .select("id, user_id, title, created_at, updated_at")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .execute()
    )

    return res.data or []


@router.get("/sessions/{session_id}", response_model=dict)
async def get_session(session_id: str, user_id: str):
    """Get one session and all messages."""

    sb = _sb_read()

    session_res = (
        sb.table("chat_sessions")
        .select("id, user_id, title, created_at, updated_at")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not session_res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    session_row = session_res.data[0]

    messages_res = (
        sb.table("chat_messages")
        .select(
            "id, session_id, user_id, question, answer, "
            "sources_json, response_time, created_at"
        )
        .eq("session_id", session_row["id"])
        .order("created_at", desc=False)
        .execute()
    )

    return {
        "session": session_row,
        "messages": messages_res.data or [],
    }


@router.post("/sessions", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_session(user_id: str, title: Optional[str] = None):
    """Create new chat session."""

    sb = _sb_write()

    now = datetime.now(timezone.utc).isoformat()

    try:
        res = (
            sb.table("chat_sessions")
            .insert({
                "user_id": user_id,
                "title": title or "New Conversation",
                "created_at": now,
                "updated_at": now,
            })
            .execute()
        )

    except Exception as exc:
        logger.exception("Failed to create session: %s", exc)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {exc}",
        ) from exc

    row = res.data[0] if res.data else {}

    return {
        "session_id": row.get("id"),
    }


@router.post("/messages", response_model=dict, status_code=status.HTTP_201_CREATED)
async def save_message(request: SaveMessageRequest):
    """
    Save chat message.

    session_id must reference:
    chat_sessions.id
    """

    sb = _sb_write()

    now = datetime.now(timezone.utc).isoformat()

    # ─────────────────────────────────────────────────────────
    # Verify session ownership
    # ─────────────────────────────────────────────────────────

    verified = (
        sb.table("chat_sessions")
        .select("id")
        .eq("id", request.session_id)
        .eq("user_id", request.user_id)
        .execute()
    )

    if not verified.data:
        logger.warning(
            "save_message blocked: session_id=%s not found for user_id=%s",
            request.session_id,
            request.user_id,
        )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Session '{request.session_id}' "
                f"not found for user '{request.user_id}'."
            ),
        )

    session_pk = verified.data[0]["id"]

    # ─────────────────────────────────────────────────────────
    # Insert message
    # ─────────────────────────────────────────────────────────

    try:
        res = (
            sb.table("chat_messages")
            .insert({
                "id": str(uuid4()),
                "session_id": session_pk,
                "user_id": request.user_id,
                "question": request.question,
                "answer": request.answer,
                "sources_json": request.sources_json,
                "response_time": request.response_time,
                "created_at": now,
            })
            .execute()
        )

        # Update parent session updated_at
        (
            sb.table("chat_sessions")
            .update({
                "updated_at": now,
            })
            .eq("id", session_pk)
            .execute()
        )

    except Exception as exc:
        logger.exception("save_message insert failed: %s", exc)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save message: {exc}",
        ) from exc

    return res.data[0] if res.data else {"status": "saved"}


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_session(session_id: str, user_id: str = Query(..., description="UUID of the user")):
    """Delete session + messages."""

    sb = _sb_write()

    verified = (
        sb.table("chat_sessions")
        .select("id")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not verified.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    session_pk = verified.data[0]["id"]

    # delete child messages
    (
        sb.table("chat_messages")
        .delete()
        .eq("session_id", session_pk)
        .execute()
    )

    # delete session
    (
        sb.table("chat_sessions")
        .delete()
        .eq("id", session_pk)
        .execute()
    )

    return None


__all__ = ["router"]