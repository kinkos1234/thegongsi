# Contributing

comad-stock에 기여 환영합니다. 아직 초기 단계라 작은 PR도 반영됩니다.

## 개발 셋업

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # DART_API_KEY, ANTHROPIC_API_KEY 등
pytest tests/

# Frontend
cd ../frontend
npm install
npm run dev  # http://localhost:3333
```

## 커밋 컨벤션

- `feat:` 새 기능 / `fix:` 버그 / `refactor:` 리팩터링 / `docs:` 문서 / `test:` 테스트
- 한국어·영어 혼용 OK. 제목 50자 이내.

## PR 체크리스트

- [ ] `pytest tests/` 녹색
- [ ] `npm run typecheck` 녹색
- [ ] PRD 위배 없는지 확인 (`PRD/01_PRD.md` §9 비목표 참고)
- [ ] 투자자문 프롬프트 금지 — AI는 정보 제공만

## 도메인 주의

- **DART API 한도:** 10,000 req/day. 수집 로직은 증분 + 백오프 필수.
- **LLM 비용:** Haiku 우선, Sonnet은 DD 메모·Cypher 생성에만.
- **투자자문 금지:** 매수/매도 추천 프롬프트 금지. bull/bear 논리만 제공.

## 토론

- Issues: 버그·기능 제안
- Discussions: 디자인·로드맵
