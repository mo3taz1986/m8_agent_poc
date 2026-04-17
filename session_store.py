from __future__ import annotations

import json
import logging
import uuid
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Lazy Redis import ──────────────────────────────────────────────────────
# redis is an optional dependency. If it is not installed or REDIS_URL is
# not set, the store falls back to an in-memory dict transparently.
try:
    import redis as redis_lib
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False

# ── Canonical stage names (lowercase) ─────────────────────────────────────
# These are the only valid stage values. Never store uppercase stage strings.
# Format for display at render time, not in stored state.
#
#   clarification
#   review_ready
#   delivery_artifacts_ready
#   execution_ready
#   jira_payload_ready
#   jira_submitted

REQUESTS_INDEX_KEY = "m8:requests_index"


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
      session_store.get(session_id)                          → Dict | None
      session_store.set(session_id, data)                    → None
      session_store.delete(session_id)                       → None
      session_store.create_session_id()                      → str
      session_store.get_requests_index()                     → Dict
      session_store.save_requests_index(index)               → None
      session_store.update_request_metadata(request_id, ...) → None
    """

    def __init__(self, redis_url: str = "", ttl_seconds: int = 86400) -> None:
        self._ttl = ttl_seconds
        self._memory: Dict[str, Dict] = {}
        self._memory_requests_index: Dict[str, Dict] = {}
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

    # ── Public interface — sessions ────────────────────────────────────────

    @staticmethod
    def create_session_id() -> str:
        """Generate a new unique session ID."""
        return str(uuid.uuid4())

    @staticmethod
    def create_request_id() -> str:
        """Generate a new unique request ID."""
        return str(uuid.uuid4())

    def get(self, session_id: str) -> Optional[Dict]:
        """
        Retrieve a session by ID. Returns None if not found or expired.
        """
        if not session_id:
            return None

        if self._redis is not None:
            return self._redis_get(self._session_key(session_id))

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
            self._redis_set(self._session_key(session_id), data)
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
                self._redis.delete(self._session_key(session_id))
            except Exception as exc:
                logger.warning("SessionStore.delete failed: %s", exc)
        else:
            self._memory.pop(session_id, None)

    @property
    def backend(self) -> str:
        """Returns 'redis' or 'memory' — useful for health checks and logging."""
        return "redis" if self._redis is not None else "memory"

    # ── Public interface — requests index ─────────────────────────────────

    def get_requests_index(self) -> Dict[str, Dict]:
        """
        Retrieve the full requests index.
        Returns an empty dict if the index does not exist yet.

        Structure:
          {
            "<request_id>": {
              "request_id": str,
              "session_id": str,
              "title": str,
              "status": str,          # mirrors session stage (lowercase)
              "last_updated": str,    # ISO timestamp
              "context_summary": str | None,
            },
            ...
          }
        """
        if self._redis is not None:
            try:
                raw = self._redis.get(REQUESTS_INDEX_KEY)
                if raw is None:
                    return {}
                return json.loads(raw)
            except Exception as exc:
                logger.warning("SessionStore.get_requests_index failed: %s", exc)
                return {}

        return dict(self._memory_requests_index)

    def save_requests_index(self, index: Dict[str, Dict]) -> None:
        """
        Persist the full requests index.
        Always pass the complete index dict — partial updates not supported.

        NOTE: This is a read-modify-write operation on a single key. For a
        single-user POC this is fine. Under concurrent multi-user load this
        would be a race condition and would need a Redis WATCH or Lua script.
        """
        if self._redis is not None:
            try:
                serialised = json.dumps(index, default=str)
                # Use the session TTL for the index too — it's always kept
                # alive as long as any session is active.
                self._redis.setex(
                    name=REQUESTS_INDEX_KEY,
                    time=self._ttl,
                    value=serialised,
                )
            except Exception as exc:
                logger.warning("SessionStore.save_requests_index failed: %s", exc)
        else:
            self._memory_requests_index = dict(index)

    def update_request_metadata(
        self,
        request_id: str,
        *,
        title: Optional[str] = None,
        status: Optional[str] = None,
        last_updated: Optional[str] = None,
        context_summary: Optional[str] = None,
        messages: Optional[List[Dict]] = None,
    ) -> None:
        """
        Patch one or more fields on an existing request record.
        Only non-None arguments are written — omitted kwargs are left unchanged.

        Usage:
          session_store.update_request_metadata(
              request_id,
              status="review_ready",
              last_updated=datetime.utcnow().isoformat(),
          )
        """
        index = self.get_requests_index()

        if request_id not in index:
            logger.warning(
                "update_request_metadata: request_id %s not found in index — skipping",
                request_id,
            )
            return

        record = index[request_id]

        if title is not None:
            record["title"] = title
        if status is not None:
            record["status"] = status
        if last_updated is not None:
            record["last_updated"] = last_updated
        if context_summary is not None:
            record["context_summary"] = context_summary
        if messages is not None:
            record["messages"] = messages

        index[request_id] = record
        self.save_requests_index(index)

    def add_request_to_index(
        self,
        request_id: str,
        session_id: str,
        title: str = "Draft Request",
        status: str = "clarification",
        last_updated: str = "",
    ) -> None:
        """
        Register a new request in the index.
        Called once at session creation in start_requirement_flow.
        """
        index = self.get_requests_index()

        index[request_id] = {
            "request_id": request_id,
            "session_id": session_id,
            "title": title,
            "status": status,
            "last_updated": last_updated,
            "context_summary": None,
            "messages": [],
        }

        self.save_requests_index(index)

    def get_request_by_id(self, request_id: str) -> Optional[Dict]:
        """Retrieve a single request record from the index."""
        return self.get_requests_index().get(request_id)

    def get_request_by_session_id(self, session_id: str) -> Optional[Dict]:
        """
        Find a request record by its associated session_id.
        Linear scan — acceptable for POC scale (small index).
        """
        for record in self.get_requests_index().values():
            if record.get("session_id") == session_id:
                return record
        return None

    # ── Redis helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _session_key(session_id: str) -> str:
        """Namespace session keys to avoid collisions with other Redis users."""
        return f"m8:session:{session_id}"

    def _redis_get(self, key: str) -> Optional[Dict]:
        try:
            raw = self._redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.warning(
                "SessionStore.get failed for key %s: %s — returning None",
                key, exc,
            )
            return None

    def _redis_set(self, key: str, data: Dict) -> None:
        try:
            serialised = json.dumps(data, default=str)
            self._redis.setex(
                name=key,
                time=self._ttl,
                value=serialised,
            )
        except Exception as exc:
            logger.warning(
                "SessionStore.set failed for key %s: %s — "
                "session may not persist across restarts",
                key, exc,
            )
