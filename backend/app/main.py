from fastapi import FastAPI

from app.routes.commodities import router as commodities_router
from app.routes.mag7 import router as mag7_router

app = FastAPI(title="Ekonomi Dashboard API", version="0.1.0")

app.include_router(commodities_router)
app.include_router(mag7_router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "data_source": "yahoo_finance",
        "last_update": None,
    }
