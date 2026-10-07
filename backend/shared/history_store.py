import os
import time
import uuid
from dataclasses import dataclass, asdict
from typing import List, Optional

from shared.gcp_credentials import init_firebase

HISTORY_STORE_BACKEND = os.environ.get("HISTORY_STORE", "memory")
HISTORY_RETENTION_SECONDS = int(os.environ.get("HISTORY_RETENTION_SECONDS", str(60 * 60)))  # 1 hour, NFR-06

_firestore_client = None
_memory_store: List[dict] = []  # only used when HISTORY_STORE_BACKEND == "memory"


@dataclass
class AnalysisRecord:
    record_id: str
    session_id: str
    created_at: float          # unix timestamp, seconds
    expires_at: float          # created_at + HISTORY_RETENTION_SECONDS, for Firestore TTL
    clause_count: int
    risk_summary: dict
    term_summary: dict


def _get_firestore_client():
    """Lazily creates the Firestore client. Mirrors ocr_engine.py's
    _get_vision_client() pattern - same lazy-init, same clear-error style.

    Credentials come from shared/gcp_credentials.py: the key file from .env
    locally, or the Cloud Run service account when deployed."""
    global _firestore_client
    if _firestore_client is None:
        try:
            from firebase_admin import firestore
        except ImportError as e:
            raise RuntimeError(
                "firebase-admin is not installed. Run: pip install firebase-admin"
            ) from e

        init_firebase()
        _firestore_client = firestore.client()
    return _firestore_client


def save_analysis_record(session_id: str, clause_count: int, risk_summary: dict, term_summary: dict) -> AnalysisRecord:
    """
    Saves a summary of one analysis, tied to a session_id. Never raises -
    if saving fails (Firestore misconfigured, network issue, etc.), this
    is logged by the caller and the analysis itself still succeeds. A
    history feature failing should never block the core feature.
    """
    now = time.time()
    record = AnalysisRecord(
        record_id=uuid.uuid4().hex,
        session_id=session_id,
        created_at=now,
        expires_at=now + HISTORY_RETENTION_SECONDS,
        clause_count=clause_count,
        risk_summary=risk_summary,
        term_summary=term_summary,
    )

    if HISTORY_STORE_BACKEND == "memory":
        _memory_store.append(asdict(record))
    elif HISTORY_STORE_BACKEND == "firestore":
        client = _get_firestore_client()
        client.collection("analysis_history").document(record.record_id).set(asdict(record))
    else:
        raise RuntimeError(f"Unknown HISTORY_STORE '{HISTORY_STORE_BACKEND}'. Use 'memory' or 'firestore'.")

    return record


def get_session_history(session_id: str) -> List[dict]:
    """
    Returns records for this session_id, filtered to only the last
    HISTORY_RETENTION_SECONDS (layer 1 of the two-layer privacy design -
    see module docstring). Newest first.
    """
    cutoff = time.time() - HISTORY_RETENTION_SECONDS

    if HISTORY_STORE_BACKEND == "memory":
        matches = [
            r for r in _memory_store
            if r["session_id"] == session_id and r["created_at"] >= cutoff
        ]
    elif HISTORY_STORE_BACKEND == "firestore":
        client = _get_firestore_client()
        query = (
            client.collection("analysis_history")
            .where("session_id", "==", session_id)
            .where("created_at", ">=", cutoff)
        )
        matches = [doc.to_dict() for doc in query.stream()]
    else:
        raise RuntimeError(f"Unknown HISTORY_STORE '{HISTORY_STORE_BACKEND}'. Use 'memory' or 'firestore'.")

    matches.sort(key=lambda r: r["created_at"], reverse=True)
    return matches


def _clear_memory_store_for_testing():
    """Test-only helper - resets the in-memory store between test cases."""
    global _memory_store
    _memory_store = []