from __future__ import annotations

import json
import logging
import uuid
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ── Lazy Redis import ──────────────────────────────────────────────────────
# redis is an optional dependency. If it is not installed or REDIS_URL is
# not set, the store falls back to an in-memory dict transparently.
try:
    import redis as redis_lib
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False


class SessionStore:
    """
    Key-value session store with two backends:

    Redis (persistent)
      - Activated when REDIS_URL is set in config and redis-py is installed
      - Sessions survive server restarts and are shared across workers
      - TTL resets on every write — idle sessions expire after SESSION_TTL_SECONDS

    In-memory dict (fallback)
      - Used when REDIS_URL is empty or Redis is unreachable
      - Identical behaviour to the previous SESSION_STORE dict in ba_service.py
      - Sessions lost on server restart (original behaviour)

    All callers use the same interface regardless of backend:
      session_store.get(session_id)         → Dict | None
      session_store.set(session_id, data)   → None
      session_store.delete(session_id)      → None
      session_store.create_session_id()     → str
    """

    def __init__(self, redis_url: str = "", ttl_seconds: int = 86400) -> None:
        self._ttl = ttl_seconds
        self._memory: Dict[str, Dict] = {}
        self._redis: Optional[object] = None

        if redis_url and _REDIS_AVAILABLE:
            try:
                client = redis_lib.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=3,
                    socket_timeout=3,
                )
                # Verify connection is live before committing to Redis backend
                client.ping()
                self._redis = client
                logger.info("SessionStore: connected to Redis at %s", redis_url)
            except Exception as exc:
                logger.warning(
                    "SessionStore: could not connect to Redis (%s). "
                    "Falling back to in-memory store. "
                    "Sessions will not survive server restarts.",
                    exc,
                )
                self._redis = None
        elif redis_url and not _REDIS_AVAILABLE:
            logger.warning(
                "SessionStore: REDIS_URL is set but redis-py is not installed. "
                "Run: pip install redis. "
                "Falling back to in-memory store."
            )
        else:
            logger.info(
                "SessionStore: REDIS_URL not set. Using in-memory store. "
                "Set REDIS_URL in .env to enable persistent sessions."
            )

    # ── Public interface ───────────────────────────────────────────────────

    @staticmethod
    def create_session_id() -> str:
        """Generate a new unique session ID."""
        return str(uuid.uuid4())

    def get(self, session_id: str) -> Optional[Dict]:
        """
        Retrieve a session by ID. Returns None if not found or expired.
        """
        if not session_id:
            return None

        if self._redis is not None:
            return self._redis_get(session_id)

        return self._memory.get(session_id)

    def set(self, session_id: str, data: Dict) -> None:
        """
        Write or overwrite a session. Resets TTL on every call.
        Always pass the complete session dict — partial updates are not
        supported to keep the interface simple and Redis-compatible.
        """
        if not session_id:
            return

        if self._redis is not None:
            self._redis_set(session_id, data)
        else:
            self._memory[session_id] = data

    def delete(self, session_id: str) -> None:
        """
        Delete a session. Called when the user resets from the sidebar.
        Silent no-op if session does not exist.
        """
        if not session_id:
            return

        if self._redis is not None:
            try:
                self._redis.delete(self._key(session_id))
            except Exception as exc:
                logger.warning("SessionStore.delete failed: %s", exc)
        else:
            self._memory.pop(session_id, None)

    @property
    def backend(self) -> str:
        """Returns 'redis' or 'memory' — useful for health checks and logging."""
        return "redis" if self._redis is not None else "memory"

    # ── Redis helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _key(session_id: str) -> str:
        """Namespace all keys to avoid collisions with other Redis users."""
        return f"m8:session:{session_id}"

    def _redis_get(self, session_id: str) -> Optional[Dict]:
        try:
            raw = self._redis.get(self._key(session_id))
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.warning(
                "SessionStore.get failed for %s: %s — returning None",
                session_id, exc,
            )
            return None

    def _redis_set(self, session_id: str, data: Dict) -> None:
        try:
            serialised = json.dumps(data, default=str)
            self._redis.setex(
                name=self._key(session_id),
                time=self._ttl,
                value=serialised,
            )
        except Exception as exc:
            logger.warning(
                "SessionStore.set failed for %s: %s — "
                "session may not persist across restarts",
                session_id, exc,
            )
