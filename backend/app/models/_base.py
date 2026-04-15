"""공용 Base + 식별자 헬퍼."""
import uuid

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def gen_id() -> str:
    return uuid.uuid4().hex[:12]
