"""Tests for health check and system API."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """Health check should return 200 with system status."""
    response = await client.get("/api/v1/system/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert data["trading_mode"] == "PAPER"


@pytest.mark.asyncio
async def test_system_config(client: AsyncClient) -> None:
    """Config endpoint should return non-sensitive configuration."""
    response = await client.get("/api/v1/system/config")
    assert response.status_code == 200
    data = response.json()

    # Should have trading config
    assert data["trading"]["mode"] == "PAPER"
    assert "BTCUSDT" in data["trading"]["symbols"]
    assert "ETHUSDT" in data["trading"]["symbols"]

    # Should NOT contain secrets
    response_text = response.text
    assert "secret" not in response_text.lower() or "jwt_secret" not in response_text
    assert "api_key" not in response_text.lower()
    assert "password" not in response_text.lower()


@pytest.mark.asyncio
async def test_system_status(client: AsyncClient) -> None:
    """Status endpoint should return service connectivity info."""
    response = await client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert data["trading_mode"] == "PAPER"


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient) -> None:
    """Should be able to register a new user."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@acta.local",
            "password": "Test12345678!@",
            "role": "TRADER",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@acta.local"
    assert data["role"] == "TRADER"
    assert data["mfa_enabled"] is False


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    """Should reject duplicate email registration."""
    user_data = {
        "email": "dup@acta.local",
        "password": "Test12345678!@",
        "role": "TRADER",
    }
    # First registration should succeed
    response = await client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 201

    # Second registration with same email should fail
    response = await client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    """Should login with valid credentials."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@acta.local",
            "password": "Test12345678!@",
            "role": "TRADER",
        },
    )

    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "login@acta.local",
            "password": "Test12345678!@",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] != ""
    assert data["refresh_token"] != ""
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient) -> None:
    """Should reject invalid password."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "badpass@acta.local",
            "password": "Test12345678!@",
            "role": "TRADER",
        },
    )

    # Login with wrong password
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "badpass@acta.local",
            "password": "wrongpassword12",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient) -> None:
    """Should reject login for non-existent user."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "nobody@acta.local",
            "password": "Test12345678!@",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_password_min_length(client: AsyncClient) -> None:
    """Should reject short passwords (minimum 12 chars)."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "short@acta.local",
            "password": "short",
            "role": "TRADER",
        },
    )
    assert response.status_code == 422  # Validation error
