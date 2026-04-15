"""재시도 + exponential backoff (Karpathy: 30줄이면 충분)."""
import asyncio
import logging
from typing import Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 1.0,
    name: str = "task",
) -> T | Exception:
    """fn을 최대 attempts 회 실행. 실패 시 지수 backoff.
    모든 시도 실패해도 raise하지 않고 마지막 예외를 반환 (상위가 결정).
    """
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return await fn()
        except Exception as e:
            last_exc = e
            if i == attempts - 1:
                logger.error(f"[{name}] giving up after {attempts} attempts: {e}")
                return e
            delay = base_delay * (2 ** i)
            logger.warning(f"[{name}] attempt {i+1}/{attempts} failed ({e}); retry in {delay}s")
            await asyncio.sleep(delay)
    return last_exc  # unreachable
