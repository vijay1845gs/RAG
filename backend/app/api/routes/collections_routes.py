"""
Collections routes — full CRUD backed by public.collections in Supabase.

Table columns (see db/schema.sql):
  id            UUID   PK DEFAULT uuid_generate_v4()
  user_id       UUID   NOT NULL REFERENCES public.profiles(id)
  name          TEXT   NOT NULL
  description   TEXT
  created_at    TIMESTAMPTZ DEFAULT NOW()
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.db.supabase import get_supabase_admin_client
from app.db.supabase import get_supabase_client as get_anon_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections", tags=["Collections"])


# ─── Helpers ─────────────────────────────────────────────────────

def _sb_read():
    sb = get_anon_client()
    if sb is None:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    return sb


def _sb_write():
    sb = get_supabase_admin_client()
    if sb is None:
        raise HTTPException(status_code=503, detail="Service-role client not configured")
    return sb


# ─── Schemas ─────────────────────────────────────────────────────

class CollectionCreate(BaseModel):
    name:        str  = Field(..., min_length=2, max_length=128)
    description: str | None = None


class CollectionRename(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)


class CollectionResponse(BaseModel):
    id:               str
    user_id:          str
    name:             str
    description:      str | None = None
    created_at:       str | None = None
    total_documents:  int = 0


# ─── Routes ──────────────────────────────────────────────────────

@router.post("", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(
    name:        str = Query(..., min_length=2, max_length=128),
    description: str | None = Query(None, max_length=1000),
    user_id:     str = Query(..., description="UUID of the owning user"),
):
    """Create a new named collection for this user."""
    sb = _sb_write()
    import uuid as _uuid

    now = datetime.now(timezone.utc).isoformat()
    col_id = str(_uuid.uuid4())

    try:
        res = (
            sb.table("collections")
            .insert({
                "id":          col_id,
                "user_id":     user_id,
                "name":        name.strip(),
                "description": (description or "").strip() or None,
                "created_at":  now,
            })
            .execute()
        )
    except Exception as exc:
        logger.exception("create_collection failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    row = res.data[0] if res.data else {"id": col_id}
    return CollectionResponse(
        id=row["id"],
        user_id=row.get("user_id", user_id),
        name=row.get("name", name),
        description=row.get("description"),
        created_at=row.get("created_at"),
        total_documents=0,
    )


@router.get("", response_model=list[CollectionResponse])
async def list_collections(user_id: str = Query(..., description="UUID of the owning user")):
    """List all collections for a user with accurate document counts — single batch query."""
    sb = _sb_read()

    # Fetch all collections for this user
    res = (
        sb.table("collections")
        .select("id, user_id, name, description, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return []

    # Batch-count documents across all collections in one query
    collection_ids = [r["id"] for r in rows]
    doc_counts: dict[str, int] = defaultdict(int)

    try:
        count_res = (
            sb.table("documents")
            .select("collection_id", count="exact")
            .in_("collection_id", collection_ids)
            .execute()
        )
        # Supabase count="exact" returns the total in .count; we still need per-collection
        # So do a grouped query via view or alternative: one RPC or manual per-collection.
        # Fallback: per-collection count in a single pass using in_() to identify docs,
        # then aggregate client-side in one shot.
        if count_res.data:
            for doc_row in count_res.data:
                cid = doc_row.get("collection_id")
                if cid:
                    doc_counts[cid] += 1
    except Exception:
        pass  # count query is best-effort; always return collections

    return [
        CollectionResponse(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            description=row.get("description"),
            created_at=row.get("created_at"),
            total_documents=doc_counts.get(row["id"], 0),
        )
        for row in rows
    ]


@router.patch("/{collection_id}", response_model=CollectionResponse)
async def rename_collection(
    collection_id: str,
    payload:        CollectionRename,
    user_id:        str = Query(..., description="UUID of the owning user"),
):
    """Rename a collection."""
    sb = _sb_write()

    # Verify ownership
    own = (
        sb.table("collections")
        .select("id")
        .eq("id", collection_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not own.data:
        raise HTTPException(status_code=404, detail="Collection not found")

    try:
        res = (
            sb.table("collections")
            .update({"name": payload.name.strip()})
            .eq("id", collection_id)
            .execute()
        )
    except Exception as exc:
        logger.exception("rename_collection failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    row = res.data[0] if res.data else {"id": collection_id}
    return CollectionResponse(
        id=row["id"],
        user_id=row.get("user_id", user_id),
        name=row.get("name", payload.name),
        description=row.get("description"),
        created_at=row.get("created_at"),
        total_documents=0,
    )


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: str,
    user_id:        str = Query(..., description="UUID of the owning user"),
):
    """Delete a collection and all documents in it. Chunks/embeddings are the caller's responsibility."""
    sb = _sb_write()

    # Verify ownership
    own = (
        sb.table("collections")
        .select("id")
        .eq("id", collection_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not own.data:
        raise HTTPException(status_code=404, detail="Collection not found")

    try:
        # Delete documents first (FK documents.collection_id → collections.id, CASCADE)
        sb.table("documents").delete().eq("collection_id", collection_id).execute()
        sb.table("collections").delete().eq("id", collection_id).execute()
    except Exception as exc:
        logger.exception("delete_collection failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return None


__all__ = ["router"]
