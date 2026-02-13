from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.cache import cache
from app.core.provider_monitor import provider_monitor
from app.core.scheduler import scheduler
from app.core.time import to_stockholm
from app.db.migrations import upgrade_to_head
from app.db.session import database_url
from app.routes.config import router as config_router
from app.routes.commodities import router as commodities_router
from app.routes.inflation import router as inflation_router
from app.routes.mag7 import router as mag7_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    upgrade_to_head()
    await scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()


app = FastAPI(title="Ekonomi Dashboard API", version="0.1.0", lifespan=lifespan)

app.include_router(commodities_router)
app.include_router(mag7_router)
app.include_router(inflation_router)
app.include_router(config_router)


@app.get("/api/health")
def health():
    last_update = cache.last_update()
    last_success_by_module = {
        module: to_stockholm(value) for module, value in cache.last_success_by_module().items()
    }
    return {
        "status": "ok",
        "data_source": "yahoo_finance",
        "provider": {"name": "yfinance"},
        "cache": cache.stats(),
        "is_stale": cache.is_globally_stale(),
        "last_update": to_stockholm(last_update),
        "last_success_by_module": last_success_by_module,
        "provider_stats": provider_monitor.snapshot(),
        "database": {"enabled": True, "url": database_url()},
    }
