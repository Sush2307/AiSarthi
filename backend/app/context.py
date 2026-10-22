"""Conversation session manager for AI Sarthi.

Maintains multi-turn context, verified evidence history, and filter states
to support conversational follow-ups, evidence summaries, and comparisons.
"""
from __future__ import annotations
import re
import threading
import time
from typing import Any

SESSION_TTL_SECONDS = 3600  # 1 hour session lifetime

class SessionState:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.last_question: str | None = None
        self.last_answer: str | None = None
        self.last_records: list[dict[str, Any]] = []
        self.last_filters: dict[str, Any] = {}
        self.last_intent: str | None = None
        self.turns: list[dict[str, Any]] = []
        self.updated_at: float = time.time()

    def update(
        self,
        question: str,
        answer: str,
        records: list[dict[str, Any]],
        filters: dict[str, Any],
        intent: str,
    ) -> None:
        self.last_question = question
        self.last_answer = answer
        if records:
            self.last_records = list(records)
        self.last_filters = dict(filters)
        self.last_intent = intent
        self.turns.append({
            "question": question,
            "answer": answer,
            "record_count": len(records),
            "filters": dict(filters),
            "intent": intent,
            "timestamp": time.time(),
        })
        self.updated_at = time.time()

    @property
    def has_records(self) -> bool:
        return bool(self.last_records and len(self.last_records) > 0)

    @property
    def last_indicator(self) -> str | None:
        if self.last_filters.get("indicator"):
            return self.last_filters["indicator"]
        if self.last_records and self.last_records[0].get("indicator"):
            return self.last_records[0]["indicator"]
        return None

    @property
    def last_state(self) -> str | None:
        if self.last_filters.get("state"):
            return self.last_filters["state"]
        if self.last_records and (self.last_records[0].get("state") or self.last_records[0].get("state_standard")):
            return self.last_records[0].get("state") or self.last_records[0].get("state_standard")
        return None

    @property
    def last_district(self) -> str | None:
        if self.last_filters.get("district"):
            return self.last_filters["district"]
        if self.last_records and (self.last_records[0].get("district") or self.last_records[0].get("district_clean")):
            return self.last_records[0].get("district") or self.last_records[0].get("district_clean")
        return None

    @property
    def last_source(self) -> str | None:
        if self.last_filters.get("source"):
            return self.last_filters["source"]
        if self.last_records and self.last_records[0].get("source"):
            return self.last_records[0]["source"]
        return None

    @property
    def last_year(self) -> str | None:
        if self.last_filters.get("year"):
            return self.last_filters["year"]
        if self.last_records and self.last_records[0].get("year"):
            return self.last_records[0]["year"]
        return None


class ConversationManager:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = threading.Lock()

    def get_or_create(self, session_id: str | None) -> SessionState:
        sid = (session_id or "default_client").strip()
        now = time.time()
        with self._lock:
            # Clean up expired sessions periodically
            if len(self._sessions) > 500:
                expired = [k for k, s in self._sessions.items() if now - s.updated_at > SESSION_TTL_SECONDS]
                for k in expired:
                    del self._sessions[k]

            if sid not in self._sessions:
                self._sessions[sid] = SessionState(sid)
            return self._sessions[sid]

    @staticmethod
    def is_summary_request(question: str) -> bool:
        q = question.lower().strip()
        patterns = [
            r"summariz(e|ing)",
            r"give (me )?a summary",
            r"explain (these |this |the )?(results|records|data|numbers?)",
            r"what does this (number|statistic|value) mean",
            r"what do these (numbers|statistics|values) mean",
            r"in simple (language|terms|words)",
            r"plain (language|english)",
            r"break (this|these) down",
            r"simplify (this|these)",
        ]
        return any(re.search(p, q) for p in patterns)

    @staticmethod
    def is_source_or_metadata_request(question: str) -> bool:
        q = question.lower().strip()
        patterns = [
            r"what is the (data )?source",
            r"(what|which) (data )?source",
            r"(data )?source and (reporting )?period",
            r"where is this (data|record|number) from",
            r"what (reporting )?period",
            r"what year (is this|does this cover)",
            r"who collected this",
            r"how was this (data )?collected",
            r"tell me about the source",
            r"(source|period) for (this|these)",
        ]
        return any(re.search(p, q) for p in patterns)

    @staticmethod
    def is_location_followup(question: str) -> tuple[bool, str | None]:
        q = question.lower().strip()
        m = re.search(r"^(?:what about|how about|and in|now show|compare with|compare to)\s+([a-zA-Z\s]+)[?.]*$", q)
        if m:
            candidate = m.group(1).strip()
            # Exclude non-location follow-up terms
            if candidate not in ["that", "this", "these", "it", "the source", "the numbers", "simple terms", "detail"]:
                return True, candidate
        return False, None


# Global singleton instance
session_manager = ConversationManager()
