"""
Redis-backed chat response cache.

Design:
  - Redis is used ONLY for chat caching (not as Celery result backend)
  - Key format: chat:{collection_id}:{rag_mode}:{response_style}:{question_hash}
    - rag_mode and response_style are included because changing 'precise' → 'creative'
      must produce different cached answers
  - TTL: configurable (default 300 seconds / 5 minutes)
  - Redis unavailable: silent fallback — never crash the app

Usage:
  from app.services.cache_service import ChatCacheService
  cache = ChatCacheService()
  cached = cache.get(collection_id, question, rag_mode, response_style)
  cache.set(collection_id, question, rag_mode, response_style, response_data)
"""

import hashlib
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ChatCacheService:
    """
    Thin Redis wrapper for chat response caching.

    Instantiate once at the module level (lazy Redis connection).
    All methods are safe to call when Redis is unavailable — they
    log a warning and return None / False instead of raising.
    """

    _PREFIX = "chat"

    def __init__(self) -> None:
        self._client = None
        self._connected = False
        self._ttl: int = 300  # overridden from settings on first use

    def _ensure_client(self) -> bool:
        """Lazily connect to Redis. Returns True if connected."""
        if self._connected:
            return True
        try:
            import redis
            from app.core.config import settings
            self._ttl = settings.REDIS_CACHE_TTL
            self._client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            self._client.ping()
            self._connected = True
            logger.info("Redis cache connected. url=%s ttl=%ds", settings.REDIS_URL, self._ttl)
        except Exception as exc:
            logger.warning("Redis cache unavailable — falling back to no-cache mode. error=%s", exc)
            self._connected = False
        return self._connected

    # ─── Key construction ─────────────────────────────────────────────────────

    def _make_key(
        self,
        collection_id: str,
        question: str,
        rag_mode: str,
        response_style: str,
        temperature: Optional[float] = None,
        top_k: Optional[int] = None,
        show_sources: Optional[bool] = None,
        preferred_model: Optional[str] = None,
    ) -> str:
        """
        Build a cache key that covers all dimensions that affect the answer.

        Changing retrieval, generation, model identity, or source visibility
        settings produces a different key.
        """
        # Hash the question to keep keys short and safe
        q_hash = hashlib.sha256(question.strip().lower().encode()).hexdigest()[:20]
        safe_col = (collection_id or "default").replace(":", "_")
        safe_mode = (rag_mode or "balanced").replace(":", "_")
        safe_style = (response_style or "professional").replace(":", "_")
        safe_temp = "none" if temperature is None else f"{float(temperature):.4g}"
        safe_top_k = "none" if top_k is None else str(top_k)
        safe_sources = "default" if show_sources is None else str(bool(show_sources)).lower()
        safe_model = (preferred_model or "default").replace(":", "_")
        return (
            f"{self._PREFIX}:{safe_col}:{safe_mode}:{safe_style}:"
            f"temp={safe_temp}:topk={safe_top_k}:sources={safe_sources}:"
            f"model={safe_model}:{q_hash}"
        )

    # ─── Public API ───────────────────────────────────────────────────────────

    def get(
        self,
        collection_id: str,
        question: str,
        rag_mode: str = "balanced",
        response_style: str = "professional",
        temperature: Optional[float] = None,
        top_k: Optional[int] = None,
        show_sources: Optional[bool] = None,
        preferred_model: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Return cached chat response dict or None on miss / Redis unavailable.

        The returned dict is ready to be re-serialized as a ChatResponse.
        """
        if not self._ensure_client():
            return None
        try:
            key = self._make_key(
                collection_id,
                question,
                rag_mode,
                response_style,
                temperature,
                top_k,
                show_sources,
                preferred_model,
            )
            raw = self._client.get(key)
            if raw:
                logger.debug("Cache HIT. key=%s", key)
                return json.loads(raw)
            logger.debug("Cache MISS. key=%s", key)
            return None
        except Exception as exc:
            logger.warning("Cache GET error (falling back): %s", exc)
            return None

    def set(
        self,
        collection_id: str,
        question: str,
        rag_mode: str,
        response_style: str,
        response_data: dict,
        temperature: Optional[float] = None,
        top_k: Optional[int] = None,
        show_sources: Optional[bool] = None,
        preferred_model: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Store a chat response in Redis.

        Returns True on success, False on failure (Redis unavailable).
        """
        if not self._ensure_client():
            return False
        try:
            key = self._make_key(
                collection_id,
                question,
                rag_mode,
                response_style,
                temperature,
                top_k,
                show_sources,
                preferred_model,
            )
            effective_ttl = ttl if ttl is not None else self._ttl
            self._client.setex(key, effective_ttl, json.dumps(response_data, default=str))
            logger.debug("Cache SET. key=%s ttl=%ds", key, effective_ttl)
            return True
        except Exception as exc:
            logger.warning("Cache SET error (non-fatal): %s", exc)
            return False

    def invalidate_collection(self, collection_id: str) -> int:
        """
        Delete all cached responses for a collection.

        Called when a new document is uploaded to ensure stale answers
        are evicted. Returns number of keys deleted.
        """
        if not self._ensure_client():
            return 0
        try:
            pattern = f"{self._PREFIX}:{collection_id.replace(':', '_')}:*"
            keys = self._client.keys(pattern)
            if keys:
                deleted = self._client.delete(*keys)
                logger.info("Invalidated %d cache entries for collection=%s", deleted, collection_id)
                return deleted
            return 0
        except Exception as exc:
            logger.warning("Cache invalidation error (non-fatal): %s", exc)
            return 0

    def get_stats(self) -> dict:
        """
        Return basic Redis info for the Dashboard queue stats endpoint.

        Keys returned: connected, used_memory_human, keyspace_hits,
                       keyspace_misses, cache_hit_rate (%).
        """
        if not self._ensure_client():
            return {"connected": False}
        try:
            info = self._client.info()
            hits = info.get("keyspace_hits", 0)
            misses = info.get("keyspace_misses", 0)
            total = hits + misses
            hit_rate = round(hits / total * 100, 1) if total > 0 else 0.0
            return {
                "connected": True,
                "used_memory_human": info.get("used_memory_human", "—"),
                "keyspace_hits": hits,
                "keyspace_misses": misses,
                "cache_hit_rate": hit_rate,
                "connected_clients": info.get("connected_clients", 0),
            }
        except Exception as exc:
            logger.warning("Cache stats error: %s", exc)
            return {"connected": False, "error": str(exc)}

    def ping(self) -> bool:
        """Return True if Redis is reachable."""
        if not self._ensure_client():
            return False
        try:
            return bool(self._client.ping())
        except Exception:
            return False


# Module-level singleton — import this in chat_service and routes
chat_cache = ChatCacheService()

__all__ = ["ChatCacheService", "chat_cache"]
