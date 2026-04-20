"""In-memory session store keyed by phone number with JSON snapshot persistence."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path("sessions")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _blank_session(phone: str) -> dict[str, Any]:
    now = _now()
    return {
        "phone": phone,
        "language": None,
        "consent_given": False,
        "consent_version": None,
        "consent_pending_since": None,
        "messages": [],
        "user_segment": None,
        "active_intent": None,
        "flow_state": {},
        "handoff_state": "bot_active",
        "created_at": now,
        "updated_at": now,
    }


class SessionStore:
    def __init__(self, max_history: int = 20) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}
        self._max_history = max_history
        SESSIONS_DIR.mkdir(exist_ok=True)
        self._load_snapshots()

    # -- public API --------------------------------------------------------

    def get(self, phone: str) -> dict[str, Any]:
        if phone not in self._sessions:
            self._sessions[phone] = _blank_session(phone)
        return self._sessions[phone]

    def save(self, phone: str) -> None:
        """Persist current session to disk as JSON."""
        session = self._sessions.get(phone)
        if session is None:
            return
        session["updated_at"] = _now()
        path = SESSIONS_DIR / f"{_safe_filename(phone)}.json"
        path.write_text(json.dumps(session, ensure_ascii=False, indent=2))

    def add_message(self, phone: str, role: str, content: str, media_url: str = None, media_type: str = None) -> None:
        session = self.get(phone)
        msg = {"role": role, "content": content, "timestamp": _now()}
        if media_url:
            msg["media_url"] = media_url
        if media_type:
            msg["media_type"] = media_type
        session["messages"].append(msg)
        # sliding window trim
        if len(session["messages"]) > self._max_history:
            session["messages"] = session["messages"][-self._max_history :]
        self.save(phone)

    def get_history(self, phone: str) -> list[dict[str, str]]:
        """Return message history in Claude-compatible format."""
        session = self.get(phone)
        return [
            {"role": m["role"], "content": m["content"]} for m in session["messages"]
        ]

    def get_existing(self, phone: str) -> dict[str, Any] | None:
        """Return session if it exists, None otherwise (no auto-create)."""
        return self._sessions.get(phone)

    def get_all(self) -> dict[str, dict[str, Any]]:
        """Return all sessions (for dashboard list view)."""
        return dict(self._sessions)

    def clear(self, phone: str) -> None:
        self._sessions[phone] = _blank_session(phone)
        self.save(phone)

    # -- internals ---------------------------------------------------------

    def _load_snapshots(self) -> None:
        for path in SESSIONS_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                phone = data.get("phone", "")
                if phone:
                    self._sessions[phone] = data
            except Exception:
                logger.warning("Failed to load session snapshot: %s", path)


def _safe_filename(phone: str) -> str:
    return phone.replace("+", "").replace(":", "_")


# Module-level singleton — ensures all imports share the same instance
_singleton: SessionStore | None = None


def get_session_store() -> SessionStore:
    """Return the shared SessionStore singleton."""
    global _singleton
    if _singleton is None:
        _singleton = SessionStore()
    return _singleton
