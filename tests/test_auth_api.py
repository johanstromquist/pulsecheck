import uuid

import pytest

from pulsecheck.auth import generate_api_key, hash_api_key


@pytest.mark.asyncio
async def test_create_api_key(client):
    """Creating an API key returns the plaintext key once."""
    resp = await client.post("/api/v1/auth/keys", json={"name": "test-key"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-key"
    assert data["is_active"] is True
    assert "key" in data
    assert data["key"].startswith("pc_")
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_list_api_keys(client):
    """Listing API keys does not expose the plaintext key."""
    resp1 = await client.post("/api/v1/auth/keys", json={"name": "key-1"})
    api_key = resp1.json()["key"]
    await client.post("/api/v1/auth/keys", json={"name": "key-2"}, headers={"X-API-Key": api_key})

    resp = await client.get("/api/v1/auth/keys", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    for key_data in data:
        assert "key" not in key_data
        assert "name" in key_data


@pytest.mark.asyncio
async def test_revoke_api_key(client):
    """Revoking an API key sets is_active to False."""
    create_resp = await client.post("/api/v1/auth/keys", json={"name": "revoke-me"})
    data = create_resp.json()
    key_id = data["id"]
    api_key = data["key"]

    # Create a second key so we still have a valid key after revoking the first
    resp2 = await client.post("/api/v1/auth/keys", json={"name": "keep-me"}, headers={"X-API-Key": api_key})
    api_key2 = resp2.json()["key"]

    resp = await client.delete(f"/api/v1/auth/keys/{key_id}", headers={"X-API-Key": api_key2})
    assert resp.status_code == 200
    assert resp.json()["detail"] == "API key revoked"

    # Verify it's revoked in the list
    list_resp = await client.get("/api/v1/auth/keys", headers={"X-API-Key": api_key2})
    revoked = [k for k in list_resp.json() if k["id"] == key_id]
    assert len(revoked) == 1
    assert revoked[0]["is_active"] is False


@pytest.mark.asyncio
async def test_revoke_nonexistent_key(client):
    """Revoking a non-existent key returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/api/v1/auth/keys/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_middleware_allows_public_endpoints(client):
    """Public endpoints should be accessible without an API key."""
    # Health endpoint
    resp = await client.get("/health")
    assert resp.status_code == 200

    # Status endpoint
    resp = await client.get("/api/v1/status")
    assert resp.status_code == 200

    # Version endpoint
    resp = await client.get("/api/v1/version")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_middleware_bootstrap_mode(client):
    """When no API keys exist, all endpoints should be accessible (bootstrap mode)."""
    # No keys created yet, so all endpoints should work
    resp = await client.post("/api/v1/services", json={
        "name": "bootstrap-test",
        "url": "https://bootstrap.example.com",
    })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_middleware_requires_key_after_creation(client):
    """After creating an API key, protected endpoints require authentication."""
    # Create an API key first
    create_resp = await client.post("/api/v1/auth/keys", json={"name": "auth-key"})
    api_key = create_resp.json()["key"]

    # Without key - should be rejected
    resp = await client.get("/api/v1/services")
    assert resp.status_code == 401
    assert "Missing X-API-Key" in resp.json()["detail"]

    # With valid key - should succeed
    resp = await client.get("/api/v1/services", headers={"X-API-Key": api_key})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_middleware_rejects_invalid_key(client):
    """An invalid API key should be rejected."""
    # Create a key so auth is enforced
    await client.post("/api/v1/auth/keys", json={"name": "real-key"})

    resp = await client.get("/api/v1/services", headers={"X-API-Key": "pc_invalid_key"})
    assert resp.status_code == 401
    assert "Invalid or inactive" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_middleware_rejects_revoked_key(client):
    """A revoked API key should be rejected."""
    # Create and revoke a key
    create_resp = await client.post("/api/v1/auth/keys", json={"name": "to-revoke"})
    data = create_resp.json()
    key_id = data["id"]
    api_key = data["key"]

    # Key works before revocation
    resp = await client.get("/api/v1/services", headers={"X-API-Key": api_key})
    assert resp.status_code == 200

    # Revoke
    await client.delete(f"/api/v1/auth/keys/{key_id}", headers={"X-API-Key": api_key})

    # Key should no longer work
    resp = await client.get("/api/v1/services", headers={"X-API-Key": api_key})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_public_endpoints_accessible_with_key_active(client):
    """Public endpoints remain accessible even after API keys are created."""
    await client.post("/api/v1/auth/keys", json={"name": "some-key"})

    resp = await client.get("/health")
    assert resp.status_code == 200

    resp = await client.get("/api/v1/status")
    assert resp.status_code == 200


def test_hash_api_key():
    """hash_api_key should produce consistent hashes."""
    key = "pc_test_key_123"
    h1 = hash_api_key(key)
    h2 = hash_api_key(key)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest


def test_generate_api_key():
    """Generated keys should have the pc_ prefix and be unique."""
    k1 = generate_api_key()
    k2 = generate_api_key()
    assert k1.startswith("pc_")
    assert k2.startswith("pc_")
    assert k1 != k2
