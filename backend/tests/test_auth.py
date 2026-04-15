"""인증 5 케이스 — stock-strategy 테스트 패턴 이식."""
import pytest


@pytest.mark.asyncio
async def test_register(client):
    r = await client.post("/api/auth/register", json={
        "email": "a@test.com", "password": "pw12345678", "name": "테스트"
    })
    assert r.status_code == 200
    data = r.json()
    assert "token" in data
    assert data["user"]["email"] == "a@test.com"


@pytest.mark.asyncio
async def test_register_duplicate(client):
    payload = {"email": "dup@test.com", "password": "pw12345678", "name": "dup"}
    await client.post("/api/auth/register", json=payload)
    r = await client.post("/api/auth/register", json=payload)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_login(client):
    await client.post("/api/auth/register", json={
        "email": "b@test.com", "password": "pw12345678", "name": "b"
    })
    r = await client.post("/api/auth/login", json={"email": "b@test.com", "password": "pw12345678"})
    assert r.status_code == 200
    assert "token" in r.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/auth/register", json={
        "email": "c@test.com", "password": "pw12345678", "name": "c"
    })
    r = await client.post("/api/auth/login", json={"email": "c@test.com", "password": "wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me(client):
    r = await client.post("/api/auth/register", json={
        "email": "d@test.com", "password": "pw12345678", "name": "디"
    })
    token = r.json()["token"]
    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "d@test.com"
