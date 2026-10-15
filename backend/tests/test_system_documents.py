"""Tests for system health endpoints, document uploading, and error cases."""

import io
import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.user import User


@pytest.mark.asyncio
async def test_health_and_readiness(client: AsyncClient):
    # Health endpoint
    health_resp = await client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "healthy"

    # Readiness endpoint
    ready_resp = await client.get("/ready")
    assert ready_resp.status_code == 200
    assert ready_resp.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_document_lifecycle(
    client: AsyncClient,
    teacher_user: User,
    student_user: User,
):
    teacher_token = create_access_token(subject=teacher_user.id, role=teacher_user.role.value)
    student_token = create_access_token(subject=student_user.id, role=student_user.role.value)

    # Create subject
    subj_resp = await client.post(
        "/api/v1/subjects",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "name": "Distributed Systems",
            "code": "CS401",
            "description": "Raft, Paxos, and Vector Clocks",
        },
    )
    assert subj_resp.status_code == 201
    subject_id = subj_resp.json()["id"]

    # Teacher uploads a markdown document
    file_content = b"# Distributed Consensus\nRaft is a consensus algorithm..."
    files = {"file": ("consensus.md", io.BytesIO(file_content), "text/markdown")}

    upload_resp = await client.post(
        f"/api/v1/subjects/{subject_id}/documents",
        headers={"Authorization": f"Bearer {teacher_token}"},
        files=files,
    )
    assert upload_resp.status_code == 201
    doc_data = upload_resp.json()
    doc_id = doc_data["id"]
    assert doc_data["filename"] == "consensus.md"
    assert doc_data["ingestion_status"] == "pending"

    # Check status endpoint
    status_resp = await client.get(
        f"/api/v1/documents/{doc_id}/status",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "pending"

    # List documents for subject
    list_docs_resp = await client.get(
        f"/api/v1/subjects/{subject_id}/documents",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert list_docs_resp.status_code == 200
    docs = list_docs_resp.json()
    assert len(docs) == 1
    assert docs[0]["id"] == doc_id

    # Delete document
    del_resp = await client.delete(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert del_resp.status_code == 204
