# Projektstatus 5

## Projektöversikt

`Ekonomi_dashboard` är en monorepo med:

- `backend/` (FastAPI)
- `frontend/` (Next.js)
- `config/` (instrumentlista i YAML)
- `scripts/` (test/körflöden och deploy-/verifieringsskript)

Syftet är en finansiell dashboard för flera enheter (laptop/mobil/tablet) med:

- marknadsdata (råvaror + Mag7) från Yahoo Finance
- inflation (Sverige + USA) från FRED

## Vad projektet gör idag

- Hämtar marknadsdata från Yahoo Finance via `yfinance`.
- Hämtar inflationsserier från FRED (CSV) och beräknar YoY i backend.
- Exponerar backend-API:
  - `/api/health`
  - `/api/commodities/summary`
  - `/api/commodities/series?id=<id>&range=1m|3m|1y`
  - `/api/mag7/summary`
  - `/api/inflation/summary`
  - `/api/inflation/series?id=<id>&range=1m|3m|6m|1y`
  - `/api/config`
- Returnerar summary/series med utökad `meta` inklusive `stale_reason` och `age_seconds`.
- Normaliserar publika timestamps till `Europe/Stockholm`.
- Använder in-memory cache (TTL 60s) med global stale-threshold och partial responses vid upstream-fel.
- Kör schemalagd cache-refresh i backend var 60:e sekund (kan stängas av via `APP_DISABLE_SCHEDULER`).
- Persistar scheduler- och datapunkter i SQLite via SQLAlchemy + Alembic.
- Frontend använder TanStack Query med polling/refetch för dashboardmoduler.
- Har Docker/Compose-upplägg för frontend + backend och ett härdat remote deploy-skript.

## Utvecklat så här långt

- End-to-end-flöde mellan frontend och backend är etablerat.
- Backend:
  - DB-lager med migrationer (`alembic`) och SQLite-runtime
  - tabeller för instrument, snapshots, series points, `job_run`, `provider_event`
  - retry/backoff + jitter i providerlager
  - provider-specifik rate-limit-kontroll (konfigurerbar via env)
  - stale-policy + health-metadata (`provider_stats`, `last_success_by_module`)
  - strukturerade scheduler-loggar med event-fält (`scheduler.refresh.*`)
- Frontend:
  - TanStack Query i app-layout (`QueryClientProvider`)
  - query-baserad datahämtning för `Råvaror`, `Mag 7`, `Inflation`
  - fortsatt UI med tabbar, KPI-kort, graf, tabell och statusbadges
- Drift/Release:
  - `scripts/update-remote-docker.sh` med fast-forward-only deployflöde och commit-validering
  - `scripts/check-readme-sync.sh` + GitHub Actions-workflow för att hålla README/scripting usage i sync
  - `scripts/test-all.sh` kör nu även docs/shell-sync-check före backend/frontendtester
- Dokumentation:
  - README uppdaterad med arkitekturskiss, env-tabeller, migrationsflöde och driftguide

## Vad som återstår  

- Publik exponering är fortfarande utanför V1-scope:
  - ingen publik auth/access control i applikationslagret
  - ingen edge-rate-limiting för internettrafik (endast upstream-skydd i providerlager)
- Drift för 24/7-tillgänglighet kräver fortfarande en alltid-på host (eller separat deployment-miljö).
- `npm audit` rapporterar moderata frontend-sårbarheter som bör hanteras i en separat dependency-hardening-runda.

## Mognadsgrad just nu

Projektet är i praktiken på V1-nivå för privat drift (LAN/Tailscale):

- kärnflödet är robust med persistens, retry/rate-limit och observability,
- dokumentation och deployflöde är reproducerbara,
- testkedjan är grön (`./scripts/test-all.sh`: backend 22 tester, frontend 11 tester),
men publik internetdrift och säkerhetshärdning återstår som nästa större fas.
