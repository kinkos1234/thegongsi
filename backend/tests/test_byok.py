import os
import pytest
from cryptography.fernet import Fernet


async def _register(client, email) -> str:
    r = await client.post("/api/auth/register", json={"email": email, "password": "pw12345678", "name": "b"})
    return r.json()["token"]


@pytest.mark.asyncio
async def test_status_without_server_key(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.field_encryption_key", "")
    t = await _register(client, "b1@k.com")
    r = await client.get("/api/byok/status", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200
    assert r.json() == {"configured_server_side": False, "anthropic": False, "openai": False}


@pytest.mark.asyncio
async def test_set_without_server_key(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.field_encryption_key", "")
    t = await _register(client, "b2@k.com")
    r = await client.post("/api/byok/", json={"anthropic_key": "sk-ant-test"},
                          headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_set_and_clear(client, monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr("app.config.settings.field_encryption_key", key)
    t = await _register(client, "b3@k.com")
    h = {"Authorization": f"Bearer {t}"}

    r = await client.post("/api/byok/", json={"anthropic_key": "sk-ant-xxx"}, headers=h)
    assert r.status_code == 200

    r = await client.get("/api/byok/status", headers=h)
    assert r.json()["anthropic"] is True
    assert r.json()["openai"] is False

    r = await client.delete("/api/byok/", headers=h)
    assert r.status_code == 200

    r = await client.get("/api/byok/status", headers=h)
    assert r.json()["anthropic"] is False
