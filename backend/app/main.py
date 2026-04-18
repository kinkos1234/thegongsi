import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import auth, calendar, companies, disclosures, memos, watchlist, alerts, qa, byok, quotes, earnings, feedback, graph, admin_jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    # httpx/httpcore 는 기본 INFO 레벨에서 요청 URL을 통째로 로그에 찍는다.
    # scan_ex_dates_v2.py 등에서 fetch 호출 시 `?crtfc_key=<평문>` 가 로그에
    # 남고, admin_jobs가 그 stderr tail을 Actions 응답에 넣으면 public
    # repo의 Actions 로그에 유출됨 (2026-04-18 사건). WARNING으로 올린다.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    await init_db()
    yield


app = FastAPI(title="The Gongsi API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    max_age=3600,
)


# 기본 보안 헤더 (Medium 19 대응)
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer-when-downgrade"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(companies.router, prefix="/api/companies", tags=["companies"])
app.include_router(disclosures.router, prefix="/api/disclosures", tags=["disclosures"])
app.include_router(memos.router, prefix="/api/memos", tags=["memos"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["watchlist"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(qa.router, prefix="/api/qa", tags=["qa"])
app.include_router(byok.router, prefix="/api/byok", tags=["byok"])
app.include_router(quotes.router, prefix="/api/quotes", tags=["quotes"])
app.include_router(earnings.router, prefix="/api/earnings", tags=["earnings"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["feedback"])
app.include_router(graph.router, prefix="/api/graph", tags=["graph"])
app.include_router(calendar.router, prefix="/api/calendar", tags=["calendar"])
app.include_router(admin_jobs.router, prefix="/api/admin/jobs", tags=["admin-jobs"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
