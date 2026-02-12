# Projektstatus 3

## Projektöversikt

`Ekonomi_dashboard` är en monorepo med:

- `backend/` (FastAPI)
- `frontend/` (Next.js)
- `config/` (instrumentlista i YAML)
- `scripts/` (test/körflöden och lokala run-skript)

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
- Returnerar summary med `meta` (`source`, `cached`, `fetched_at`).
- Använder in-memory cache (TTL 60s) och partial responses (stale per instrument vid fel).
- Frontend visar:
  - tabbar: `Råvaror`, `Mag 7`, `Inflation`
  - 6 KPI-kort + vald graf + tabell för både `Råvaror` och `Mag 7`
  - sortering i Mag7-tabellen (fält + riktning)
  - statusbadges per modul under tabb-raden (`Fresh/Partial/Stale/Offline`)
  - auto-refresh (60s)
- Kan köras lokalt och nås från andra egna enheter via LAN/Tailscale utan Docker.

## Utvecklat så här långt

- End-to-end-flöde mellan frontend och backend är etablerat.
- Backend:
  - provider-lager för Yahoo + FRED
  - beräkningslogik för KPI-fält (`day_abs`, `day_pct`, `w1_pct`, `ytd_pct`, `y1_pct`)
  - inflationstjänst som omvandlar FRED-data till YoY-serier
  - cache och health-status
  - moduler för `commodities`, `mag7`, `inflation`
- Konfiguration:
  - instrumentlista i `config/instruments.example.yaml`
  - inflation-instrument för FRED-serier (`CP0000SEM086NEST`, `CPIAUCSL`)
- Frontend:
  - tabbaserad vy med dynamiskt KPI-/graf-/tabellinnehåll
  - header förenklad (ingen sökruta), rubrik `Marknadsöversikt`
  - status per modul under tabbar
  - tema-toggle (dark/light)
  - färglogik enligt spec (positiv grön, negativ röd)
  - råvarutabell uppdaterad med `TID`, enhet i första kolumnen och tydlig `abs + %` i `+/-`
  - on-demand/LAN-körning med `dev:lan` och `start:lan`
- Backend:
  - schemalagd uppdatering var 60:e sekund via bakgrundsjobb
  - API-anrop använder i första hand förvärmd cache med request-driven fallback vid cache miss
- Drift:
  - `scripts/run-backend.sh`, `scripts/run-frontend.sh`, `scripts/run-dev.sh`
  - `frontend/.env.example` och `API_BASE_URL` mot intern backend (`127.0.0.1:8000`)
  - Docker/Compose-upplägg för isolerad körning på annan Linux-maskin
- Test:
  - backendtester: 15 tester
  - frontendtester: 11 tester
  - samlad testkörning via `./scripts/test-all.sh`

## Vad som återstår

- Svenska talformat enligt spec är struket som krav.
  - Punkt som decimaltecken är accepterat.
  - Tusentalsavgränsare (mellanslag) krävs inte.
- Stale-threshold enligt spec (t.ex. flagga stale efter längre utebliven uppdatering) saknar explicit implementation.
- Tidsstämpel i Europe/Stockholm enligt spec saknas som tydlig backendstandard.
- Skydd mot rate limits är inte fullt utbyggt:
  - retry/backoff saknas
  - max-anrop per tidsenhet (konfigurerbart) saknas
- Persistent cache/databas saknas (cache är volatil vid omstart).
- SQLite i MVP (och senare PostgreSQL) enligt spec är ännu inte implementerat.
- Loggning enligt spec saknas/är ofullständig:
  - antal instrument ok/fail
  - senaste uppdatering per jobb
  - upstream-fel och retry-statistik
- Auth/rate-limiting saknas om projektet ska öppnas för fler än egna enheter.
- Eventuell deployment/24-7-host behövs om appen ska vara tillgänglig när laptop är avstängd.
- TanStack Query (arkitekturval i spec) används inte i nuvarande frontend.
- README har några formateringsdetaljer att städa (exempelvis `1;`, `2;`, `3;` i körsektionen).

## Mognadsgrad just nu

Projektet är i en stabil MVP+ fas:

- kärnflödet fungerar i produktionlik lokal miljö,
- testtäckningen är bra för nuvarande scope,
- funktionerna för Råvaror, Mag7 och Inflation är integrerade i UI,
men flera krav från originalspecen (persistent lagring och driftkrav) återstår.
