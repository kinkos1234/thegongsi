"""지배구조 샘플 시드 — 삼성·현대차 계열 단순화 예시.

공시 기반 추출 파이프라인이 LLM API 키와 문서 fetch를 필요로 하므로,
개발·시연용 샘플 데이터를 즉시 넣기 위한 스크립트.

운영 데이터는 `extract_from_disclosures(ticker)` 파이프라인으로 대체.

사용:
    cd backend && python -m scripts.seed_governance
"""
import asyncio
from datetime import date

from app.database import async_session, init_db
from app.models.tables import CorporateOwnership, Insider, MajorShareholder


AS_OF = date.today().strftime("%Y-%m-%d")


SHAREHOLDERS = [
    # 삼성전자
    {"ticker": "005930", "holder_name": "이재용", "holder_type": "person", "stake_pct": 1.63},
    {"ticker": "005930", "holder_name": "삼성물산", "holder_type": "corp",
     "holder_ticker": "028260", "stake_pct": 5.01},
    {"ticker": "005930", "holder_name": "삼성생명", "holder_type": "corp",
     "holder_ticker": "032830", "stake_pct": 8.51},
    {"ticker": "005930", "holder_name": "국민연금", "holder_type": "fund", "stake_pct": 8.63},
    # 삼성물산
    {"ticker": "028260", "holder_name": "이재용", "holder_type": "person", "stake_pct": 17.97},
    {"ticker": "028260", "holder_name": "삼성SDI", "holder_type": "corp",
     "holder_ticker": "006400", "stake_pct": 0.22},
    # 삼성생명
    {"ticker": "032830", "holder_name": "삼성물산", "holder_type": "corp",
     "holder_ticker": "028260", "stake_pct": 19.34},
    # SK하이닉스
    {"ticker": "000660", "holder_name": "SK", "holder_type": "corp",
     "holder_ticker": "034730", "stake_pct": 20.07},
    {"ticker": "000660", "holder_name": "국민연금", "holder_type": "fund", "stake_pct": 8.99},
]

INSIDERS = [
    # 삼성전자
    {"ticker": "005930", "person_name": "이재용", "role": "회장",
     "classification": "exec", "is_registered": True},
    {"ticker": "005930", "person_name": "한종희", "role": "대표이사 부회장",
     "classification": "exec", "is_registered": True},
    {"ticker": "005930", "person_name": "김기남", "role": "사외이사",
     "classification": "outside", "is_registered": True},
    # SK하이닉스
    {"ticker": "000660", "person_name": "곽노정", "role": "대표이사",
     "classification": "exec", "is_registered": True},
]

# 기업간 지분 (parent → child)
CORP_OWNERSHIP = [
    {"parent_ticker": "028260", "child_ticker": "005930",
     "parent_name": "삼성물산", "child_name": "삼성전자", "stake_pct": 5.01},
    {"parent_ticker": "032830", "child_ticker": "005930",
     "parent_name": "삼성생명", "child_name": "삼성전자", "stake_pct": 8.51},
    {"parent_ticker": "005930", "child_ticker": "006400",
     "parent_name": "삼성전자", "child_name": "삼성SDI", "stake_pct": 19.58},
    {"parent_ticker": "006400", "child_ticker": "028260",
     "parent_name": "삼성SDI", "child_name": "삼성물산", "stake_pct": 0.22},
    {"parent_ticker": "028260", "child_ticker": "032830",
     "parent_name": "삼성물산", "child_name": "삼성생명", "stake_pct": 19.34},
    # SK
    {"parent_ticker": "034730", "child_ticker": "000660",
     "parent_name": "SK", "child_name": "SK하이닉스", "stake_pct": 20.07},
]


async def run():
    await init_db()
    async with async_session() as db:
        for row in SHAREHOLDERS:
            db.add(MajorShareholder(**row, as_of=AS_OF))
        for row in INSIDERS:
            db.add(Insider(**row, as_of=AS_OF))
        for row in CORP_OWNERSHIP:
            db.add(CorporateOwnership(**row, as_of=AS_OF))
        await db.commit()
    print(
        f"Seeded governance data as_of {AS_OF}: "
        f"{len(SHAREHOLDERS)} shareholders, "
        f"{len(INSIDERS)} insiders, "
        f"{len(CORP_OWNERSHIP)} ownership edges."
    )


if __name__ == "__main__":
    asyncio.run(run())
