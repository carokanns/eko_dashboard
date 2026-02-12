from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.cache import cache
from app.core.scheduler import scheduler
from app.routes.commodities import router as commodities_router
from app.routes.inflation import router as inflation_router
from app.routes.mag7 import router as mag7_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()


app = FastAPI(title="Ekonomi Dashboard API", version="0.1.0", lifespan=lifespan)

app.include_router(commodities_router)
app.include_router(mag7_router)
app.include_router(inflation_router)


@app.get("/api/health")
def health():
    last_update = cache.last_update()
    return {
        "status": "ok",
        "data_source": "yahoo_finance",
        "provider": {"name": "yfinance"},
        "cache": cache.stats(),
        "last_update": last_update,
    }
