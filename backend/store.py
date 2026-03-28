"""
In-memory session store keyed by doc_id (UUID).
Holds raw ingested data between /ingest and /query calls.
Will be replaced by a vector store in Features 4-7.
"""

from typing import Dict, Any

_store: Dict[str, Any] = {}


def save(doc_id: str, data: Any) -> None:
    _store[doc_id] = data


def get(doc_id: str) -> Any | None:
    return _store.get(doc_id)


def exists(doc_id: str) -> bool:
    return doc_id in _store
