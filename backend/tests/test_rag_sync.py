"""Vector-store sync at startup and failure handling during indexing (no real ChromaDB needed)."""

from pathlib import Path
from typing import Any, List

import pytest

from app.models.document import Document, IngestionStatus
from app.models.subject import Subject
from app.models.user import User
from app.services import rag
from tests.conftest import test_async_session


class FakeCollection:
    def __init__(self, fail: bool = False) -> None:
        self.rows: dict = {}
        self.fail = fail

    def upsert(self, ids: List[str], documents: List[str], metadatas: List[dict]) -> None:
        if self.fail:
            raise RuntimeError("disk full")
        for i, doc, meta in zip(ids, documents, metadatas):
            self.rows[i] = (doc, meta)

    def get(self, where: dict, limit: int = 1) -> dict:
        ids = [i for i, (_, m) in self.rows.items() if m["document_id"] == where["document_id"]]
        return {"ids": ids[:limit]}


class FakeClient:
    def __init__(self, fail: bool = False) -> None:
        self.collections: dict = {}
        self.fail = fail

    def get_or_create_collection(self, name: str, metadata: Any = None) -> FakeCollection:
        return self.collections.setdefault(name, FakeCollection(self.fail))

    def get_collection(self, name: str) -> FakeCollection:
        if name not in self.collections:
            raise ValueError("no such collection")
        return self.collections[name]


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> rag.HybridRAGStore:
    s = rag.HybridRAGStore()
    s._chroma_client = FakeClient()
    monkeypatch.setattr(rag, "_rag_instance", s)
    monkeypatch.setattr(rag, "async_session_factory", test_async_session)
    return s


async def _add_docs(teacher: User, tmp_path: Path, names: List[str]) -> None:
    async with test_async_session() as db:
        db.add(Subject(id="subj-rag", name="OS", code="RAG1", description="", teacher_id=teacher.id))
        for n in names:
            f = tmp_path / f"{n}.txt"
            f.write_text(f"{n}: deadlock requires mutual exclusion, hold and wait, no preemption and circular wait.")
            db.add(
                Document(
                    id=n,
                    subject_id="subj-rag",
                    filename=f.name,
                    file_path=str(f),
                    file_type="txt",
                    file_size_bytes=f.stat().st_size,
                    ingestion_status=IngestionStatus.COMPLETED,
                )
            )
        await db.commit()


async def test_sync_indexes_only_documents_missing_from_the_store(
    store: rag.HybridRAGStore, teacher_user: User, tmp_path: Path
) -> None:
    await _add_docs(teacher_user, tmp_path, ["doc-a", "doc-b"])
    await store.ingest_document("subj-rag", "doc-a", tmp_path / "doc-a.txt", "doc-a.txt")  # already indexed

    assert await rag.sync_documents_into_vector_store() == 1  # only doc-b
    assert await store.has_document("subj-rag", "doc-b")
    assert await rag.sync_documents_into_vector_store() == 0  # idempotent


async def test_sync_skips_documents_whose_file_is_gone(
    store: rag.HybridRAGStore, teacher_user: User, tmp_path: Path
) -> None:
    await _add_docs(teacher_user, tmp_path, ["doc-gone"])
    (tmp_path / "doc-gone.txt").unlink()
    assert await rag.sync_documents_into_vector_store() == 0


async def test_sync_is_a_no_op_without_chromadb(store: rag.HybridRAGStore) -> None:
    store._chroma_client = None
    assert await rag.sync_documents_into_vector_store() == 0


async def test_vector_store_write_failure_marks_document_failed(
    store: rag.HybridRAGStore, teacher_user: User, tmp_path: Path
) -> None:
    store._chroma_client = FakeClient(fail=True)
    await _add_docs(teacher_user, tmp_path, ["doc-x"])

    with pytest.raises(RuntimeError, match="Vector store indexing failed"):
        await rag.ingest_document_pipeline("doc-x")

    async with test_async_session() as db:
        doc = await db.get(Document, "doc-x")
    assert doc is not None and doc.ingestion_status == IngestionStatus.FAILED
    assert "disk full" in (doc.error_message or "")
