from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import auth, companies, disclosures, memos, watchlist, alerts, qa, byok, quotes, earnings, feedback


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="comad-stock API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.get("/api/health")
async def health():
    return {"status": "ok"}
