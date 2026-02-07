# Projektstatus 1

## Projektöversikt
`Ekonomi_dashboard` är en monorepo med:
- `backend/` (FastAPI)
- `frontend/` (Next.js)
- `config/` (instrumentlista i YAML)
- `scripts/` (test/körflöden)

Syftet är en finansiell dashboard som visar råvaror och Mag7 med data från Yahoo Finance.

## Vad projektet gör idag
- Hämtar live marknadsdata via `yfinance`.
- Exponerar API:
  - `/api/health`
  - `/api/commodities/summary`
  - `/api/mag7/summary`
  - `/api/commodities/series?id=<id>&range=1m|3m|1y`
- Returnerar summary med `meta` (`source`, `cached`, `fetched_at`).
- Har in-memory cache (TTL 60s).
- Stödjer partial responses: enstaka instrument kan vara stale utan att hela endpointen faller.
- Frontend visar data för råvaror och Mag7, med:
  - auto-refresh (60s)
  - sök/filter
  - Mag7-sortering på YTD
  - statusvisning (Fresh/Partial/Stale/Offline)

## Utvecklat så här långt
- End-to-end-koppling mellan frontend och backend.
- Riktig dataprovider + beräkningslogik för nyckeltal.
- Tester utbyggda:
  - Backend: API, cache, partial-fel, health, series, beräkningar.
  - Frontend: rendering, fallback, stale/live, filter/sort.
- Samlat testskript: `scripts/test-all.sh`.
- LAN/Tailscale-körning utan Docker:
  - `scripts/run-backend.sh` (127.0.0.1:8000)
  - `scripts/run-frontend.sh` (0.0.0.0:3000)
  - `scripts/run-dev.sh` (båda)
- README uppdaterad med drift- och åtkomstflöde (LAN + Tailscale).

## Vad som återstår
- Funktionellt innehåll för flikarna `Inflation` och `Grafer` (nu mest UI-placeholder).
- Persistent cache/databas (idag endast in-memory).
- Auth/rate-limiting om appen ska delas bredare.
- Deployment/24-7-hosting om du vill slippa att laptopen måste vara igång.
- Eventuell städning av frontend-audit-varningar i dev/test dependencies (`npm audit`).

## Mognadsgrad just nu
Du har en fungerande v1-MVP som går att använda på laptop, mobil och tablet (LAN/Tailscale), med bra testtäckning för kärnflödet.
