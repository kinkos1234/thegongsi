"""pytest 설정. 테스트는 in-memory SQLite."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import engine, init_db
from app.main import app
from app.models.tables import Base


@pytest_asyncio.fixture
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
