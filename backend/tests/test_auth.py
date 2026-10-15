"""Unit and integration tests for authentication."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    # 1. Register a student
    reg_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "teststudent@vivaiq.edu",
            "password": "strongpassword123",
            "full_name": "Test Student",
            "role": "student",
        },
    )
    assert reg_response.status_code == 201
    data = reg_response.json()
    assert data["email"] == "teststudent@vivaiq.edu"
    assert data["full_name"] == "Test Student"
    assert "id" in data

    # 2. Login
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "teststudent@vivaiq.edu",
            "password": "strongpassword123",
        },
    )
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]

    # 3. Access /me endpoint
    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 200
    me_data = me_response.json()
    assert me_data["email"] == "teststudent@vivaiq.edu"

    # 4. Refresh token
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 200
    new_token_data = refresh_response.json()
    assert "access_token" in new_token_data


@pytest.mark.asyncio
async def test_invalid_login(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "nonexistent@vivaiq.edu",
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401
