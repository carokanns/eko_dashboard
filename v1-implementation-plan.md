# V1-roadmap: Ekonomi Dashboard (baserat på `status4.md` + Kombinerad Spec V1)

## Sammanfattning
Målet är att gå från stabil MVP+ till en full V1 med robust drift för privat nät (LAN/Tailscale), utan publik-exponering som primärt mål. Planen låser dessa beslut:
1. `TanStack Query` införs fullt ut i frontend.
2. Persistens införs med `SQLite` nu och `PostgreSQL`-redo design.
3. Backend får retry/backoff, rate-limit-kontroll, stale-hantering, strukturerad loggning och bättre observability.
4. Nuvarande API-kompatibilitet behålls, med kontrollerade tillägg för metadata/diagnostik.

## Omfattning och målbild
1. Slutföra kvarvarande spec-krav som saknas enligt `status4.md`.
2. Hålla befintliga endpoints stabila för UI-kompatibilitet.
3. Göra datalager och scheduler tillförlitliga vid omstart/fel.
4. Leverera tydliga drift- och testkriterier för V1-release.

## Låsta designval
1. Backend stack: FastAPI + SQLAlchemy + Alembic + SQLite (MVP/V1), PostgreSQL-kompatibel schema-design.
2. Retry/backoff: `tenacity` med exponentiell backoff + jitter.
3. Rate limit-kontroll: provider-specifik token-bucket i backend (Yahoo/FRED separat), konfigurerbar via env.
4. Frontend data: `@tanstack/react-query` med polling/refetch, och borttag av `router.refresh`-loop.
5. Tidszonstandard: samtliga publika timestamps normaliseras till `Europe/Stockholm`.
6. Privat drift först: auth/rate limiting för publik internet skjuts till efter V1 men förbereds strukturellt.

## Publika API-/interface-ändringar
1. Behåll oförändrat:
   - `GET /api/health`
   - `GET /api/commodities/summary`
   - `GET /api/commodities/series`
   - `GET /api/mag7/summary`
   - `GET /api/inflation/summary`
   - `GET /api/inflation/series`
2. Utöka `meta` i summary/series med:
   - `stale_reason: "none" | "global_threshold" | "provider_error" | "no_recent_success"`
   - `age_seconds: number`
3. Utöka `/api/health` med:
   - `last_success_by_module` (`commodities`, `mag7`, `inflation`)
   - `provider_stats` (ok/fail/retries senaste fönster)
4. Lägg till:
   - `GET /api/config` (whitelistad instrumentkonfig, inga hemligheter)
5. Bakåtkompatibilitet:
   - existerande fält bibehålls; nya fält är additiva.

## Datamodell och persistens
1. Nya tabeller:
   - `instrument`
   - `quote_snapshot`
   - `series_point`
   - `job_run`
   - `provider_event`
2. Nycklar/index:
   - unik på (`instrument_id`, `timestamp`, `series_type`)
   - index på `module`, `fetched_at`, `job_name`, `status`
3. Migrationer:
   - initial Alembic migration för SQLite
   - databas-URL via `APP_DATABASE_URL`, default SQLite-fil

## Genomförandeplan (sekventiell)
1. Fas 1: Infrastrukturgrund
   - Inför DB-lager, Alembic, repositories, settings.
   - Flytta cache- och scheduler-beroenden till service interfaces.
   - Klara kriterier: backend startar med migration auto-run i dev.
2. Fas 2: Robust datainhämtning
   - Implementera retry/backoff + rate limiter i providerlager.
   - Lägg till max-anrop/tidsfönster per provider via env.
   - Klara kriterier: simulerade upstream-fel ger partial response, ej total fail.
3. Fas 3: Stale och metadata
   - Enhetlig stale-policy (global threshold + modulspecifik senaste success).
   - Normalisera Stockholm-tid i alla response-paths.
   - Lägg till nya `meta`-fält och health-utökningar.
   - Klara kriterier: stale växlar korrekt efter tröskel och syns i API.
4. Fas 4: Frontend till TanStack Query
   - Inför `QueryClientProvider` i app-layout.
   - Ersätt server-fetch i `page.tsx` med query hooks i dashboard-vy.
   - Polling/refetch 60s + felhantering per modul + cache stale-time.
   - Klara kriterier: UI-beteende oförändrat funktionellt men drivs av query-lager.
5. Fas 5: Observability och loggning
   - Strukturerade loggar för jobbkörningar, instrument ok/fail, retries.
   - Exponera lättviktiga driftsiffror via `/api/health`.
   - Klara kriterier: varje scheduler-körning lämnar spårbar sammanfattning.
6. Fas 6: Dokumentation och release-hardening
   - Uppdatera README, env-tabeller, arkitekturskiss, driftguide.
   - Rätta formatteringsfel i körsektion (`1;` -> korrekt numrering).
   - Klara kriterier: ny miljö kan startas reproducerbart via README + compose.

## Testfall och acceptanskriterier
1. Backend enhetstester
   - retry/backoff triggas och stoppar efter maxförsök
   - rate limiter blockerar över gräns och återhämtar efter fönster
   - stale-beräkning med exakt threshold-tester
   - timestamp alltid `Europe/Stockholm` i svar
2. Backend integrationstester
   - scheduler skriver `job_run` + `provider_event`
   - partial responses vid enstaka ticker-fel
   - cache + DB fallback fungerar efter omstart
3. Frontend tester
   - query-baserad rendering för alla tre moduler
   - refetch/polling uppdaterar status badges korrekt
   - fel i en modul påverkar inte övriga moduler
4. E2E-smoke
   - `docker compose up` ger fungerande dashboard
   - `/api/health` visar rimliga stats efter 2 scheduler-cykler
5. Definition of Done för V1
   - alla tester gröna i `./scripts/test-all.sh`
   - inga regressions i befintliga endpoints
   - dokumenterade env-variabler för cache/stale/retry/rate-limit/DB

## Antaganden och valda standarder
1. `status4.md` gäller som kravtolkning före äldre specdetaljer.
2. Svensk decimal-komma/tusentalsmellanslag förblir utanför scope i denna V1.
3. Privat nät (LAN/Tailscale) är primär driftmodell; publik auth är inte blockerande för V1.
4. SQLite är primär runtime i V1; PostgreSQL-stöd säkras genom kompatibelt schema och migrationsdisciplin.
5. Nuvarande tabs (`Råvaror`, `Mag 7`, `Inflation`) behålls; ingen ny top-level modul tillkommer i V1.
