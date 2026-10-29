"""Retrieval-Augmented Generation (RAG) knowledge pipeline.

Supports PDF, DOCX, TXT, and Markdown parsing, semantic chunking with overlap,
vector embedding, and grounded source citation retrieval.
"""

import math
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import logger
from app.models.document import Document, IngestionStatus


class SourceReference(BaseModel):
    document_id: str
    filename: str
    page: Optional[int] = None
    chunk_index: int
    score: float
    excerpt: str


class RetrievedContext(BaseModel):
    subject_id: str
    query: str
    sources: List[SourceReference] = []
    combined_context: str = ""


class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    subject_id: str
    filename: str
    page: Optional[int] = None
    chunk_index: int
    text: str


# ==========================================
# 1. Document Extractors
# ==========================================


def extract_text_from_pdf(file_path: Path) -> List[Tuple[Optional[int], str]]:
    """Extract pages from PDF returning (page_num, page_text)."""
    import pypdf

    pages_text: List[Tuple[Optional[int], str]] = []
    reader = pypdf.PdfReader(str(file_path))
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = clean_text(text)
        if text.strip():
            pages_text.append((idx + 1, text))
    return pages_text


def extract_text_from_docx(file_path: Path) -> str:
    """Extract paragraphs from DOCX document."""
    import docx

    doc = docx.Document(str(file_path))
    full_text = []
    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text.strip())
    return clean_text("\n\n".join(full_text))


def extract_text_from_file(file_path: Path) -> List[Tuple[Optional[int], str]]:
    """Parse document based on its extension into list of (page_or_none, text)."""
    ext = file_path.suffix.lower()

    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext == ".docx":
        text = extract_text_from_docx(file_path)
        return [(None, text)]
    else:
        # TXT or Markdown
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = clean_text(f.read())
        return [(None, text)]


def clean_text(text: str) -> str:
    """Normalize whitespace and strip excessive control characters."""
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ==========================================
# 2. Semantic Chunking
# ==========================================


def chunk_document_content(
    subject_id: str,
    document_id: str,
    filename: str,
    pages_data: List[Tuple[Optional[int], str]],
    chunk_size_words: int = 250,
    overlap_words: int = 40,
) -> List[DocumentChunk]:
    """Split text into semantic chunks of ~300 tokens with configured overlap."""
    chunks: List[DocumentChunk] = []
    global_chunk_idx = 0

    for page_num, text in pages_data:
        # Split on paragraph or sentence boundaries
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        current_words: List[str] = []

        for p in paragraphs:
            p_words = p.split()
            if not p_words:
                continue

            if len(current_words) + len(p_words) <= chunk_size_words:
                current_words.extend(p_words)
            else:
                # Flush current chunk
                if current_words:
                    chunk_text = " ".join(current_words)
                    chunks.append(
                        DocumentChunk(
                            chunk_id=f"{document_id}_{global_chunk_idx}",
                            document_id=document_id,
                            subject_id=subject_id,
                            filename=filename,
                            page=page_num,
                            chunk_index=global_chunk_idx,
                            text=chunk_text,
                        )
                    )
                    global_chunk_idx += 1

                    # Retain overlap from end of previous chunk
                    current_words = current_words[-overlap_words:] if overlap_words > 0 else []

                current_words.extend(p_words)

        if current_words:
            chunk_text = " ".join(current_words)
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{document_id}_{global_chunk_idx}",
                    document_id=document_id,
                    subject_id=subject_id,
                    filename=filename,
                    page=page_num,
                    chunk_index=global_chunk_idx,
                    text=chunk_text,
                )
            )
            global_chunk_idx += 1

    return chunks


# ==========================================
# 3. Vector Storage & Search
# ==========================================


class BaseRAGStore(ABC):
    @abstractmethod
    async def ingest_document(self, subject_id: str, document_id: str, file_path: Path, filename: str) -> int:
        pass

    @abstractmethod
    async def retrieve(self, subject_id: str, query: str, top_k: int = 4) -> RetrievedContext:
        pass

    @abstractmethod
    async def delete_document(self, subject_id: str, document_id: str) -> None:
        pass

    @abstractmethod
    def is_chroma_active(self) -> bool:
        """Check if persistent ChromaDB client is initialized and active."""
        pass


class HybridRAGStore(BaseRAGStore):
    """Production vector store using ChromaDB if available with fallback memory store."""

    def __init__(self) -> None:
        self._chroma_client = None
        self._in_memory_chunks: Dict[str, List[DocumentChunk]] = {}  # subject_id -> chunks
        self._init_chroma()

    def is_chroma_active(self) -> bool:
        return self._chroma_client is not None

    def _init_chroma(self) -> None:
        try:
            import chromadb

            persist_dir = str(settings.CHROMA_PERSIST_PATH)
            self._chroma_client = chromadb.PersistentClient(path=persist_dir)
            logger.info(f"ChromaDB persistent client initialized at '{persist_dir}'")
        except Exception as e:
            logger.warning(
                f"ChromaDB not available or failed to initialize ({e}). Operating in fast in-memory TF-IDF mode."
            )
            self._chroma_client = None

    def _get_collection_name(self, subject_id: str) -> str:
        clean_id = subject_id.replace("-", "_")
        return f"subj_{clean_id}"

    async def ingest_document(self, subject_id: str, document_id: str, file_path: Path, filename: str) -> int:
        """Parse, chunk, and embed a document into the subject's collection."""
        pages_data = extract_text_from_file(file_path)
        chunks = chunk_document_content(subject_id, document_id, filename, pages_data)

        if not chunks:
            logger.warning(f"No textual content extracted from {filename}")
            return 0

        # In-memory store
        if subject_id not in self._in_memory_chunks:
            self._in_memory_chunks[subject_id] = []
        # Remove any existing chunks for this document
        self._in_memory_chunks[subject_id] = [
            c for c in self._in_memory_chunks[subject_id] if c.document_id != document_id
        ]
        self._in_memory_chunks[subject_id].extend(chunks)

        # ChromaDB store
        if self._chroma_client:
            try:
                coll_name = self._get_collection_name(subject_id)
                collection = self._chroma_client.get_or_create_collection(
                    name=coll_name,
                    metadata={"subject_id": subject_id},
                )

                # Upsert chunks
                ids = [c.chunk_id for c in chunks]
                documents = [c.text for c in chunks]
                metadatas = [
                    {
                        "document_id": c.document_id,
                        "subject_id": c.subject_id,
                        "filename": c.filename,
                        "page": c.page or 0,
                        "chunk_index": c.chunk_index,
                    }
                    for c in chunks
                ]

                collection.upsert(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                )
                logger.info(f"Stored {len(chunks)} chunks in ChromaDB collection '{coll_name}'")
            except Exception as e:
                logger.error(f"Error upserting to ChromaDB: {e}")

        return len(chunks)

    async def retrieve(self, subject_id: str, query: str, top_k: Optional[int] = None) -> RetrievedContext:
        """Retrieve relevant source chunks for query."""
        k = top_k or settings.TOP_K_RETRIEVAL
        sources: List[SourceReference] = []

        if self._chroma_client:
            try:
                coll_name = self._get_collection_name(subject_id)
                collection = self._chroma_client.get_collection(coll_name)
                results = collection.query(
                    query_texts=[query],
                    n_results=k,
                )
                if results and results.get("documents") and results["documents"][0]:
                    docs = results["documents"][0]
                    metas = results["metadatas"][0] if results.get("metadatas") else []
                    distances = results["distances"][0] if results.get("distances") else []

                    for i, doc_text in enumerate(docs):
                        meta = metas[i] if i < len(metas) else {}
                        dist = distances[i] if i < len(distances) else 0.5
                        similarity = max(0.0, round(1.0 - (dist / 2.0), 3))

                        sources.append(
                            SourceReference(
                                document_id=meta.get("document_id", "unknown"),
                                filename=meta.get("filename", "document"),
                                page=meta.get("page") if meta.get("page", 0) > 0 else None,
                                chunk_index=meta.get("chunk_index", 0),
                                score=similarity,
                                excerpt=doc_text,
                            )
                        )
            except Exception as e:
                logger.warning(f"ChromaDB retrieval fallback: {e}")

        # Fallback to in-memory TF-IDF / term-overlap if Chroma returned nothing
        if not sources and subject_id in self._in_memory_chunks:
            all_chunks = self._in_memory_chunks[subject_id]
            q_terms = set(re.findall(r"\w+", query.lower()))

            scored_chunks = []
            for chunk in all_chunks:
                c_terms = set(re.findall(r"\w+", chunk.text.lower()))
                overlap = len(q_terms.intersection(c_terms))
                score = overlap / max(1, math.sqrt(len(q_terms) * len(c_terms)))
                scored_chunks.append((score, chunk))

            scored_chunks.sort(key=lambda x: x[0], reverse=True)
            for score, chunk in scored_chunks[:k]:
                sources.append(
                    SourceReference(
                        document_id=chunk.document_id,
                        filename=chunk.filename,
                        page=chunk.page,
                        chunk_index=chunk.chunk_index,
                        score=round(score, 3),
                        excerpt=chunk.text,
                    )
                )

        combined = "\n\n---\n\n".join([f"[{s.filename} P.{s.page or 1}]: {s.excerpt}" for s in sources])

        return RetrievedContext(
            subject_id=subject_id,
            query=query,
            sources=sources,
            combined_context=combined,
        )

    async def delete_document(self, subject_id: str, document_id: str) -> None:
        if subject_id in self._in_memory_chunks:
            self._in_memory_chunks[subject_id] = [
                c for c in self._in_memory_chunks[subject_id] if c.document_id != document_id
            ]

        if self._chroma_client:
            try:
                coll_name = self._get_collection_name(subject_id)
                collection = self._chroma_client.get_collection(coll_name)
                collection.delete(where={"document_id": document_id})
            except Exception as e:
                logger.warning(f"ChromaDB delete error: {e}")


_rag_instance: Optional[BaseRAGStore] = None


def get_rag_store() -> BaseRAGStore:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = HybridRAGStore()
    return _rag_instance


async def ingest_document_pipeline(document_id: str) -> int:
    """Asynchronous background ingestion pipeline for an uploaded document."""
    async with async_session_factory() as db:
        stmt = select(Document).where(Document.id == document_id)
        doc = (await db.execute(stmt)).scalar_one_or_none()
        if not doc:
            raise ValueError(f"Document '{document_id}' not found")

        doc.ingestion_status = IngestionStatus.PROCESSING
        await db.commit()

        try:
            rag_service = get_rag_store()
            chunk_count = await rag_service.ingest_document(
                subject_id=doc.subject_id,
                document_id=doc.id,
                file_path=Path(doc.file_path),
                filename=doc.filename,
            )

            doc.chunk_count = chunk_count
            doc.ingestion_status = IngestionStatus.COMPLETED
            doc.error_message = None
            await db.commit()
            logger.info(f"Successfully ingested document '{doc.filename}' ({chunk_count} chunks)")
            return chunk_count
        except Exception as e:
            logger.error(f"Ingestion failed for document '{doc.filename}': {e}")
            doc.ingestion_status = IngestionStatus.FAILED
            doc.error_message = str(e)
            await db.commit()
            raise
