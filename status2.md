# Projektstatus 2

## Projektöversikt

`Ekonomi_dashboard` är en monorepo med:

- `backend/` (FastAPI)
- `frontend/` (Next.js)
- `config/` (instrumentlista i YAML)
- `scripts/` (test/körflöden och lokala run-skript)

Syftet är en finansiell dashboard för flera enheter (laptop/mobil/tablet) med data från Yahoo Finance.

## Vad projektet gör idag

- Hämtar marknadsdata från Yahoo Finance via `yfinance`.
- Exponerar backend-API:
  - `/api/health`
  - `/api/commodities/summary`
  - `/api/commodities/series?id=<id>&range=1m|3m|1y`
  - `/api/mag7/summary`
  - `/api/inflation/summary`
  - `/api/inflation/series?id=<id>&range=1m|3m|1y`
  - `/api/charts/series?id=<id>&range=1m|3m|1y`
- Returnerar summary med `meta` (`source`, `cached`, `fetched_at`).
- Använder in-memory cache (TTL 60s) och partial responses (stale per instrument vid fel).
- Frontend visar live-data för råvaror och Mag7 med:
  - auto-refresh (60s)
  - sök/filter
  - Mag7-sortering på YTD
  - statusetiketter (Fresh/Partial/Stale/Offline)
- Kan köras lokalt och nås från andra egna enheter via LAN/Tailscale utan Docker.

## Utvecklat så här långt

- End-to-end-flöde mellan frontend och backend är etablerat.
- Backend:
  - provider-lager för Yahoo
  - beräkningslogik för KPI-fält (`day_abs`, `day_pct`, `w1_pct`, `ytd_pct`, `y1_pct`)
  - cache och health-status
  - moduler för `commodities`, `mag7`, `inflation`, `charts`
- Konfiguration:
  - instrumentlista i `config/instruments.example.yaml`
  - inflation-instrument tillagda (`TIP`, `VTIP`)
- Frontend:
  - tabbaserad vy med dynamiskt KPI-/tabellinnehåll för råvaror och Mag7
  - on-demand/LAN-körning med `dev:lan` och `start:lan`
- Drift:
  - `scripts/run-backend.sh`, `scripts/run-frontend.sh`, `scripts/run-dev.sh`
  - `frontend/.env.example` och `API_BASE_URL` mot intern backend (`127.0.0.1:8000`)
- Test:
  - backendtester utökade till 14 tester (inkl inflation/charts)
  - frontendtester utökade till 8 tester
  - samlad testkörning via `./scripts/test-all.sh`

## Vad som återstår

- Frontend är ännu inte kopplad till de nya backendmodulerna `inflation` och `charts` (API finns, UI-integration saknas).
- Design och funktion för specifika inflation/graf-vyer behöver definieras och implementeras.
- Tema-toggle (dark/light) saknas i frontend trots att det är MVP-krav i specen.
- Svenska talformat enligt spec saknas/är ofullständigt:
  - decimal-komma
  - tusentalsavgränsare (mellanslag)
- Färglogik enligt spec (positiv grön, negativ röd) är inte fullt implementerad/verifierad.
- Råvarutabellen är inte fullt spec-komplett:
  - kolumn `TID` saknas
  - enhet i första kolumnen enligt spec saknas
  - tydlig visning av `abs + %` i `+/-` behöver säkras
- Backend saknar schemalagd uppdatering (spec: var 60:e sekund); nuvarande upplägg är request-driven med cache.
- Stale-threshold enligt spec (t.ex. flagga stale efter längre utebliven uppdatering) saknar explicit implementation.
- Tidsstämpel i Europe/Stockholm enligt spec saknas som tydlig backendstandard.
- Skydd mot Yahoo rate limits är inte fullt utbyggt:
  - retry/backoff saknas
  - max-anrop per tidsenhet (konfigurerbart) saknas
- Persistent cache/databas saknas (cache är volatil vid omstart).
- SQLite i MVP (och senare PostgreSQL) enligt spec är ännu inte implementerat.
- Loggning enligt spec saknas/är ofullständig:
  - antal instrument ok/fail
  - senaste uppdatering per jobb
  - Yahoo-fel och retry-statistik
- Auth/rate-limiting saknas om projektet ska öppnas för fler än egna enheter.
- Eventuell deployment/24-7-host behövs om appen ska vara tillgänglig när laptop är avstängd.
- Docker-compose-leverabel enligt spec (frontend + backend + db) saknas.
- TanStack Query (arkitekturval i spec) används inte i nuvarande frontend.
- README har några formateringsdetaljer att städa (exempelvis `1;`, `2;`, `3;` i körsektionen).

## Mognadsgrad just nu

Projektet är i en stabil MVP+ fas:

- kärnflödet fungerar i produktionlik lokal miljö,
- testtäckningen är bra för nuvarande scope,
- backend har nu utökats för nästa funktionsområde (inflation/charts),
men full användarupplevelse för dessa nya moduler återstår i frontend.
