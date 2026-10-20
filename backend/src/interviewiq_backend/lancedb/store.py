from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from interviewiq_backend.core.config import get_settings
from interviewiq_backend.services.llm.openrouter import OpenRouterClient, local_fallback_embed

logger = logging.getLogger(__name__)

TABLE_NAME = "interview_experiences"


def _repo_seed_path() -> Path:
    # backend/src/interviewiq_backend/lancedb/store.py -> repo root knowledge/
    return Path(__file__).resolve().parents[4] / "knowledge" / "seed" / "interview_experiences.jsonl"


def _load_seed_records() -> list[dict[str, Any]]:
    path = _repo_seed_path()
    if not path.exists():
        # Also accept .json
        alt = path.with_suffix(".json")
        if alt.exists():
            return json.loads(alt.read_text())
        logger.warning("No seed knowledge file at %s", path)
        return []
    text = path.read_text().strip()
    if not text:
        return []
    # Support JSON array or JSONL
    if text.startswith("["):
        return json.loads(text)
    records = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


class KnowledgeStore:
    def __init__(self):
        self.settings = get_settings()
        self._db = None
        self._table = None

    def _connect(self):
        import lancedb

        self.settings.ensure_dirs()
        self._db = lancedb.connect(str(self.settings.lancedb_path))
        return self._db

    @property
    def db(self):
        if self._db is None:
            self._connect()
        return self._db

    def table_exists(self) -> bool:
        try:
            return TABLE_NAME in self.db.table_names()
        except Exception:  # noqa: BLE001
            return False

    async def ensure_seeded(self, force: bool = False) -> int:
        if self.table_exists() and not force:
            table = self.db.open_table(TABLE_NAME)
            return table.count_rows()

        records = _load_seed_records()
        if not records:
            return 0

        texts = [r["text"] for r in records]
        embeddings = await self._embed(texts)
        rows = []
        for r, emb in zip(records, embeddings):
            rows.append(
                {
                    "id": r["id"],
                    "company_id": r["company_id"],
                    "role_family": r.get("role_family", ""),
                    "round_type": r.get("round_type", ""),
                    "topics": r.get("topics", []),
                    "difficulty": r.get("difficulty", "medium"),
                    "year": int(r.get("year") or 0),
                    "text": r["text"],
                    "source_id": r.get("source_id", "seed"),
                    "vector": emb,
                }
            )

        if self.table_exists():
            self.db.drop_table(TABLE_NAME)
        self.db.create_table(TABLE_NAME, data=rows)
        logger.info("Seeded LanceDB with %s interview experiences", len(rows))
        return len(rows)

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        client = OpenRouterClient(self.settings)
        if client.api_key:
            try:
                return await client.embed(texts)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Embedding API failed, using local fallback: %s", exc)
        return local_fallback_embed(texts, dims=self.settings.embedding_dims)

    async def search(
        self,
        query: str,
        *,
        company_id: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        await self.ensure_seeded()
        if not self.table_exists():
            return []

        k = top_k or self.settings.rag_top_k
        query_vec = (await self._embed([query]))[0]
        table = self.db.open_table(TABLE_NAME)

        try:
            q = table.search(query_vec).limit(k * 3 if company_id else k)
            if company_id:
                q = q.where(f"company_id = '{company_id}'", prefilter=True)
            results = q.to_list()
        except Exception as exc:  # noqa: BLE001
            logger.warning("LanceDB filtered search failed (%s); falling back", exc)
            results = table.search(query_vec).limit(k * 3).to_list()
            if company_id:
                results = [r for r in results if r.get("company_id") == company_id]

        cleaned = []
        for r in results[:k]:
            cleaned.append(
                {
                    "id": r.get("id"),
                    "company_id": r.get("company_id"),
                    "round_type": r.get("round_type"),
                    "topics": r.get("topics", []),
                    "difficulty": r.get("difficulty"),
                    "text": r.get("text"),
                    "score": r.get("_distance"),
                }
            )
        return cleaned


_store: Optional[KnowledgeStore] = None


def get_knowledge_store() -> KnowledgeStore:
    global _store
    if _store is None:
        _store = KnowledgeStore()
    return _store
