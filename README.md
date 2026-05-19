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

Arkitekturskiss (V1):

```text
Klient (mobil/tablet/laptop)
            |
            v
     Next.js frontend (:3000)
            |
            v
   /api/dashboard/* route proxy
            |
            v
      FastAPI backend (:8000)
      |        |           |
      |        |           +--> In-memory TTL cache (snabb respons)
      |        |
      |        +--> SQLite + Alembic (persistens: instrument/snapshots/series/job_run/provider_event)
      |
      +--> Providers
            - Yahoo Finance (råvaror + Mag7)
            - FRED (inflation)
```

Miljövariabler:

Backend (`APP_*`):

| Variabel | Standardvärde | Beskrivning |
| --- | --- | --- |
| `APP_DATABASE_URL` | `sqlite:///backend/data/dashboard.db` | Databas-URL. SQLite default, kan pekas till PostgreSQL senare. |
| `APP_DISABLE_SCHEDULER` | `0` | Sätt `1/true/yes/on` för att stänga av scheduler. |
| `APP_STALE_THRESHOLD_SECONDS` | `600` | Global stale-tröskel för health/meta. |
| `APP_YAHOO_MAX_CALLS` | `120` | Max Yahoo-anrop per fönster. |
| `APP_YAHOO_PERIOD_SECONDS` | `60` | Fönsterlängd (sek) för Yahoo rate-limit. |
| `APP_FRED_MAX_CALLS` | `60` | Max FRED-anrop per fönster. |
| `APP_FRED_PERIOD_SECONDS` | `60` | Fönsterlängd (sek) för FRED rate-limit. |
| `APP_UPSTREAM_RETRY_ATTEMPTS` | `3` | Antal retry-försök mot upstream. |
| `APP_UPSTREAM_RETRY_BASE_MS` | `250` | Bas-delay i ms för exponential backoff + jitter. |

Frontend:

| Variabel | Standardvärde | Beskrivning |
| --- | --- | --- |
| `API_BASE_URL` | `http://127.0.0.1:8000` (lokalt), `http://backend:8000` (compose) | Backend-URL som Next.js server-side proxy använder. |

Migrations (Alembic):

- Kör senaste schema: `cd backend && .venv/bin/alembic -c alembic.ini upgrade head`
- Skapa ny migration: `cd backend && .venv/bin/alembic -c alembic.ini revision -m "beskrivning"`
- Rollback ett steg: `cd backend && .venv/bin/alembic -c alembic.ini downgrade -1`

Test:

- Samlad: `./scripts/test-all.sh`
- Backend: `cd backend && .venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt && .venv/bin/python -m pytest`
- Frontend: `cd frontend && npm install && npm run test`

Driftguide (privat nät):

1. Starta tjänster med Docker Compose: `docker compose up -d --build`
2. Verifiera backend health: `curl http://127.0.0.1:8000/api/health`
3. Verifiera frontend: öppna `http://<maskinens-ip>:3000`
4. Deploya uppdatering på målmaskin: `./scripts/update-remote-docker.sh`
5. Vid incident: kontrollera `docker compose logs backend frontend --tail=200`
6. Vid schemaändring: kör migration (`alembic upgrade head`) innan ny backend-version går live

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

Remote deploy (pull + rebuild):

- Kör på målmaskinen i repots rot: `./scripts/update-remote-docker.sh`
- Lås till specifik commit (CI/CD): `./scripts/update-remote-docker.sh <full-commit-hash>`
- Skriptet kräver ren git-worktree och använder fast-forward-only pull.

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
