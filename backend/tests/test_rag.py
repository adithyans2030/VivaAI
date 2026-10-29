"""Tests for RAG document parsing, chunking, and grounded source citation retrieval."""

from pathlib import Path

import pytest

from app.services.rag import (
    DocumentChunk,
    chunk_document_content,
    extract_text_from_file,
    get_rag_store,
)


@pytest.mark.asyncio
async def test_text_cleaning_and_chunking(tmp_path: Path):
    # Create sample study notes
    notes_content = """# Operating System Deadlocks

A deadlock occurs when two or more processes are unable to proceed because each is waiting for the other to release a resource.

## Coffman Conditions
Four conditions must hold simultaneously:
1. Mutual Exclusion: At least one resource must be held in a non-shareable mode.
2. Hold and Wait: A process must be concurrently holding at least one resource and requesting additional resources.
3. No Preemption: Resources cannot be forcibly preempted from a process.
4. Circular Wait: A closed chain of processes exists such that each process holds at least one resource needed by the next.

## Handling Deadlocks
Operating systems typically handle deadlocks using deadlock prevention, deadlock avoidance via Banker's algorithm, or detection and recovery.
"""
    file_path = tmp_path / "deadlocks.md"
    file_path.write_text(notes_content, encoding="utf-8")

    # 1. Parse text from file
    pages_data = extract_text_from_file(file_path)
    assert len(pages_data) == 1
    assert "Coffman Conditions" in pages_data[0][1]

    # 2. Chunk text
    chunks = chunk_document_content(
        subject_id="subj-os",
        document_id="doc-deadlocks",
        filename="deadlocks.md",
        pages_data=pages_data,
        chunk_size_words=40,
        overlap_words=10,
    )
    assert len(chunks) >= 2
    for chunk in chunks:
        assert isinstance(chunk, DocumentChunk)
        assert chunk.document_id == "doc-deadlocks"
        assert chunk.filename == "deadlocks.md"
        assert len(chunk.text) > 0


@pytest.mark.asyncio
async def test_rag_ingest_and_grounded_retrieval(tmp_path: Path):
    store = get_rag_store()

    # Create subject study guide
    content = """Process Synchronization and Concurrency Control.
The critical-section problem is to design a protocol that processes can use to cooperate.
Each process must request permission to enter its critical section.
The section of code implementing this request is the entry section.
The critical section may be followed by an exit section, and the remainder is the remainder section.
A satisfactory solution must satisfy: Mutual Exclusion, Progress, and Bounded Waiting.
Semaphores and Mutex locks are standard synchronization primitives.
"""
    doc_path = tmp_path / "sync.txt"
    doc_path.write_text(content, encoding="utf-8")

    # Ingest document
    chunk_count = await store.ingest_document(
        subject_id="cs301-test",
        document_id="doc-sync-1",
        file_path=doc_path,
        filename="sync.txt",
    )
    assert chunk_count >= 1

    # Retrieve context for a question query
    query = "What three requirements satisfy the critical section problem?"
    retrieved = await store.retrieve("cs301-test", query, top_k=2)

    assert retrieved.subject_id == "cs301-test"
    assert len(retrieved.sources) >= 1

    top_source = retrieved.sources[0]
    assert top_source.filename == "sync.txt"
    assert "critical-section" in top_source.excerpt.lower()
    assert top_source.score > 0

    # Test document deletion
    await store.delete_document("cs301-test", "doc-sync-1")
    empty_retrieval = await store.retrieve("cs301-test", query, top_k=2)
    assert len(empty_retrieval.sources) == 0
