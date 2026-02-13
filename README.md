# Ekonomi Dashboard (Monorepo)

Struktur:

- `frontend/` Next.js-app
- `backend/` FastAPI-tjänst
- `config/` instrument-konfiguration (YAML/JSON)
- `docker-compose.yml` lokal orkestrering
- `scripts/` lokala kör/test-skript

Status:

1. Frontend och backend är kopplade end-to-end.
2. Marknadsdata hämtas från Yahoo Finance via `yfinance`.
3. Inflation hämtas från FRED-serier (USA + Sverige) och beräknas som YoY i backend.
4. In-memory cache används med TTL 60 sekunder.
5. Partial responses stöds: enskilda instrument kan vara stale utan att hela endpointen faller.

API:

- `GET /api/health`
- `GET /api/commodities/summary`
- `GET /api/mag7/summary`
- `GET /api/inflation/summary`
- `GET /api/inflation/series?id=<id>&range=1m|3m|6m|1y`
- `GET /api/commodities/series?id=<id>&range=1m|3m|1y`
- `GET /api/config`

Summary-svar:

- `{ "items": [...], "meta": { "source": "yahoo_finance", "cached": boolean, "fetched_at": iso-datetime } }`
- För inflation är `meta.source` = `fred`.

Begränsningar (v1):

- SQLite används för persistens av scheduler-data.
- Ingen publik auth/rate-limit middleware (endast upstream-skydd i providerlager).
- Datakällan är Yahoo Finance och kan ge luckor/temporära fel.

Migrations (Alembic):

- Kör senaste schema: `cd backend && .venv/bin/alembic -c alembic.ini upgrade head`
- Skapa ny migration: `cd backend && .venv/bin/alembic -c alembic.ini revision -m "beskrivning"`
- Rollback ett steg: `cd backend && .venv/bin/alembic -c alembic.ini downgrade -1`

Test:

- Samlad: `./scripts/test-all.sh`
- Backend: `cd backend && .venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt && .venv/bin/python -m pytest`
- Frontend: `cd frontend && npm install && npm run test`

Körning med Docker (rekommenderat på annan Linux-maskin):

1. Bygg och starta:
- `docker compose up -d --build`

2. Öppna appen:
- `http://<maskinens-ip>:3000`

3. Stoppa:
- `docker compose down`

Notering:
- Frontend exponeras på port `3000`.
- Backend körs internt i compose-nätet och nås av frontend via `http://backend:8000`.

Körning utan Docker (LAN + Tailscale):

- Backend körs endast lokalt på laptop: `127.0.0.1:8000`
- Frontend exponeras på nätet: `0.0.0.0:3000`
- Frontend hämtar API server-side via `API_BASE_URL=http://127.0.0.1:8000`

1. Förbered frontend-env:

- `cp frontend/.env.example frontend/.env.local`

2. Starta appen on-demand:

- Båda tjänster: `./scripts/run-dev.sh`
- Endast backend: `./scripts/run-backend.sh`
- Endast frontend: `./scripts/run-frontend.sh`

3. Åtkomst:

- LAN (hemma): `http://<laptop-lan-ip>:3000`
- Tailscale (internet): `http://<tailscale-hostname-eller-ip>:3000`

Tailscale setup (egen privat åtkomst):

1. Installera Tailscale på laptop, mobil och tablet.
2. Logga in samma tailnet på alla enheter.
3. Kontrollera att enheterna syns i Tailscale admin/klient.
4. Öppna frontend-URL via laptopens tailscale-IP/hostname.

Säkerhetsgräns (viktigt):

- Exponera endast port `3000` för appen.
- Exponera inte port `8000` (backend ska vara intern).
- Ingen router-port-forwarding behövs för Tailscale.

Snabb verifiering:

1. Lokal: öppna `http://localhost:3000` på laptopen.
2. LAN: öppna `http://<laptop-lan-ip>:3000` på mobil/tablet i samma Wi-Fi.
3. Internet: stäng av Wi-Fi på mobilen och öppna Tailscale-URL.
4. Bekräfta att `http://<laptop-ip>:8000` inte är nåbar från andra enheter.
