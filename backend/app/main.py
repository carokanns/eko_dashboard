from fastapi import FastAPI

app = FastAPI(title="Ekonomi Dashboard API", version="0.1.0")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "data_source": "yahoo_finance",
        "last_update": None,
    }
