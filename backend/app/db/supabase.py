"""
Supabase / Postgres connection helper for the RAG backend.

Reads credentials from the environment via python-dotenv and
exposes two factories:
- get_supabase_client()        — anon key  (satisfies auth.uid() for reads)
- get_supabase_admin_client()  — service_role key (bypasses RLS for internal writes)
"""

import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client, Client

# Load .env from project root if present
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
load_dotenv(dotenv_path=_env_path)

SUPABASE_URL:      str = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


@lru_cache(maxsize=1)
def get_supabase_client() -> Optional[Client]:
    """Return an anon-key client (respects RLS — use for reads and authenticated ops)."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        import logging
        logging.getLogger(__name__).warning(
            "SUPABASE_URL / SUPABASE_ANON_KEY not set — Supabase client unavailable."
        )
        return None
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


@lru_cache(maxsize=1)
def get_supabase_admin_client() -> Optional[Client]:
    """Return a service-role-key client (bypasses RLS — use for internal writes only)."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        import logging
        logging.getLogger(__name__).warning(
            "SUPABASE_SERVICE_ROLE_KEY not set — admin client unavailable."
        )
        return None
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


__all__ = [
    "get_supabase_client",
    "get_supabase_admin_client",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
]
