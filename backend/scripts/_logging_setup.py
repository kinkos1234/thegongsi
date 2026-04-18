"""스크립트 공용 로깅 설정 — 외부 요청 라이브러리 로그 차단.

Why: httpx/httpcore/urllib3의 기본 INFO 로거는 `HTTP Request: GET ...?crtfc_key=<평문>`
처럼 **URL 전체를 로그에 남긴다**. 이 출력이 admin_jobs 동기 응답의 stderr_tail
에 실리면 public repo의 Actions 로그로 유출될 수 있음 (2026-04-18 DART 키 유출
사건). FastAPI 서버 쪽은 main.py lifespan에서 mute 하지만, 서브프로세스로 도는
scan_*.py 는 별 프로세스라 이 설정이 안 옮겨감 — 여기서 한 번 더.

사용:
    from _logging_setup import setup_script_logging
    setup_script_logging()
"""
from __future__ import annotations

import logging


def setup_script_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")
    # URL 평문이 남는 HTTP 클라이언트 로거는 WARNING 이상만 허용
    for name in ("httpx", "httpcore", "urllib3", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING)
