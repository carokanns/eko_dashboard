# Ekonomi Dashboard (Monorepo)

Struktur:
- `frontend/` Next.js-app
- `backend/` FastAPI-tjänst
- `config/` instrument-konfiguration (YAML/JSON)
- `docker-compose.yml` lokal orkestrering

Status:
1. Frontend och backend är kopplade end-to-end.
2. Marknadsdata hämtas från Yahoo Finance via `yfinance`.
3. In-memory cache används med TTL 60 sekunder.
4. Partial responses stöds: enskilda instrument kan vara stale utan att hela endpointen faller.

API:
- `GET /api/health`
- `GET /api/commodities/summary`
- `GET /api/mag7/summary`
- `GET /api/commodities/series?id=<id>&range=1m|3m|1y`

Summary-svar:
- `{ "items": [...], "meta": { "source": "yahoo_finance", "cached": boolean, "fetched_at": iso-datetime } }`

Begränsningar (v1):
- Ingen persistent cache eller databas.
- Ingen auth/rate-limiting.
- Datakällan är Yahoo Finance och kan ge luckor/temporära fel.

Test:
- Samlad: `./scripts/test-all.sh`
- Backend: `cd backend && .venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt && .venv/bin/python -m pytest`
- Frontend: `cd frontend && npm install && npm run test`
