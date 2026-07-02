from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.cache import cache
from app.core.provider_monitor import provider_monitor
from app.core.scheduler import scheduler
from app.core.settings import app_api_token, local_portfolio_enabled
from app.core.time import to_stockholm
from app.db.migrations import upgrade_to_head
from app.db.session import database_url
from app.routes.config import router as config_router
from app.routes.commodities import router as commodities_router
from app.routes.indexes import router as indexes_router
from app.routes.inflation import router as inflation_router
from app.routes.mag7 import router as mag7_router
from app.routes.portfolio import router as portfolio_router
from app.services.exchange_rates import refresh_startup_exchange_rates
from app.services.portfolio_data import update_portfolio_ledger_from_transactions


@asynccontextmanager
async def lifespan(_app: FastAPI):
    upgrade_to_head()
    refresh_startup_exchange_rates()
    if local_portfolio_enabled():
        update_portfolio_ledger_from_transactions()
    await scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()


app = FastAPI(title="Ekonomi Dashboard API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def require_dashboard_token(request: Request, call_next):
    token = app_api_token()
    path = request.url.path
    if token and path.startswith("/api/") and path != "/api/health":
        supplied = request.headers.get("x-dashboard-token")
        if supplied != token:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


app.include_router(commodities_router)
app.include_router(mag7_router)
app.include_router(indexes_router)
app.include_router(inflation_router)
app.include_router(config_router)
app.include_router(portfolio_router)


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
