# AGENTS.md

## Projektet i korthet

Ekonomi Dashboard är en svenskspråkig finansiell dashboard för privat bruk på laptop, mobil och surfplatta. Den samlar marknadsdata, inflation och en valfri lokal Avanza-portfölj i ett gemensamt gränssnitt.

Projektet är ett monorepo med:

- en Next.js/React-frontend i `frontend/`
- ett FastAPI-backend i `backend/`
- instrumentkonfiguration i `config/`
- lokala kör-, test- och deployflöden i `scripts/`
- Docker Compose för samlad drift

Dashboarden visar i nuläget:

- råvaror
- Magnificent 7
- globala och regionala index
- inflation för Sverige och USA
- lokalt importerade Avanza-innehav när portföljfunktionen är aktiverad
- grafer för 1, 3, 6 och 12 månader samt ett automatiskt bildspel

Marknadsdata hämtas främst från Yahoo Finance via `yfinance`. Inflation hämtas från FRED och räknas om till årstakt i backend. Avanza-data kommer från privata, lokala exporter och kompletteras med marknadspriser, fondpriser och valutakurs där det är möjligt.

## Arkitektur och dataflöde

```text
Webbläsare
    |
    v
Next.js frontend (:3000)
    |
    v
/api/dashboard/* (server-side proxy)
    |
    v
FastAPI backend (:8000)
    |-- cache + scheduler
    |-- SQLite + Alembic
    |-- Yahoo Finance / FRED / Avanza fondpriser
    `-- lokala Avanza-exporter (valfritt)
```

Frontend ska anropa backend genom proxyn i `frontend/src/app/api/dashboard/[...slug]/route.ts`, inte direkt från klienten. Det gör att backend-token stannar på serversidan. Dashboardens datahämtning och cache i webbläsaren sköts med TanStack Query i `frontend/src/app/dashboard-page.tsx`.

Backend kör migrationer vid start, värmer data via en scheduler var 60:e sekund och använder request-driven hämtning som fallback. Sammanfattningar och tidsserier sparas i cache och SQLite. Enstaka providerfel ska normalt ge partial/stale data i stället för att slå ut en hel modul.

## Viktiga kataloger och filer

| Sökväg | Ansvar |
| --- | --- |
| `frontend/src/app/dashboard-view.tsx` | Dashboardens vyer, tabeller, grafer och bildspel |
| `frontend/src/app/dashboard-page.tsx` | TanStack Query, modulhämtning och serieladdning |
| `frontend/src/lib/api.ts` | Frontendens API-typer och proxyanrop |
| `frontend/src/app/globals.css` | Globala designvariabler och komponentstilar |
| `backend/app/main.py` | FastAPI-app, middleware, routers och livscykel |
| `backend/app/routes/` | Publika API-endpoints |
| `backend/app/services/` | Domänlogik och datainhämtning |
| `backend/app/providers/` | Integrationer mot externa datakällor |
| `backend/app/core/scheduler.py` | Schemalagd refresh, cache och persistens |
| `backend/app/db/` | SQLAlchemy-sessioner, repository och migrationer |
| `backend/alembic/versions/` | Versionsstyrda databasmigrationer |
| `config/instruments.example.yaml` | Instrument, tickers, presentation och modulindelning |
| `local-data/` | Privat Avanza-data och genererade lokala artefakter; får inte committas |
| `scripts/` | Start, stopp, test och deploy |

Ämnesspecifika `*-plan.md` och originalspecifikationen i PDF är historik och beslutsunderlag. De beskriver inte alltid det aktuella implementationstillståndet. Kod, tester, `README.md` och denna fil är den primära källan för hur projektet fungerar nu.

## API

Backend exponerar följande huvudgrupper:

- `GET /api/health`
- `GET /api/config`
- `GET /api/commodities/summary` och `/series`
- `GET /api/mag7/summary` och `/series`
- `GET /api/indexes/summary` och `/series`
- `GET /api/inflation/summary` och `/series`
- `GET /api/portfolio/status`, `/summary` och `/series`

Serier använder `range=1m|3m|6m|1y`. Publika tidsstämplar normaliseras till `Europe/Stockholm`. API-ändringar ska vara bakåtkompatibla när det är rimligt; uppdatera frontendtyper och tester samtidigt när kontrakt ändras.

## Utvecklingskommandon

Från repots rot:

```bash
./scripts/run-dev.sh        # bygg/starta frontend och backend med Docker Compose
./scripts/kill-dev.sh       # stoppa lokal utvecklingskörning
./scripts/test-all.sh       # dokumentkontroll + backendtester + frontendtester
docker compose up -d --build
docker compose down
```

Backend:

```bash
cd backend
.venv/bin/python -m pytest
.venv/bin/alembic -c alembic.ini upgrade head
```

Om `.venv` saknas, skapa den och installera `requirements.txt` samt `requirements-dev.txt` innan tester körs.

Frontend:

```bash
cd frontend
npm install
npm run test
npm run lint
npm run build
```

Kör den minsta relevanta testmängden under arbetet och `./scripts/test-all.sh` för breda eller riskfyllda ändringar. Nya beteenden och buggrättningar ska få regressionstester. Kontrollera även `git diff --check` före commit.

## Kod- och ändringsprinciper

- Bevara monorepots befintliga struktur och följ närliggande kodstil.
- Håll UI-text på svenska. Interna typer, variabler och API-fält är normalt på engelska.
- Lägg datainhämtning och beräkningar i backend; håll frontend fokuserad på hämtning, presentation och interaktion.
- Återanvänd typerna i `frontend/src/lib/api.ts` och Pydantic-modellerna i `backend/app/models/` i stället för parallella kontrakt.
- Behåll partial/stale-beteendet. Ett fel för ett instrument ska inte utan god anledning göra hela modulsvaret oanvändbart.
- Respektera providerernas retry- och rate-limit-lager. Lägg inte till oreglerade parallella upstream-anrop.
- Databasschema ändras genom en ny Alembic-migration; redigera inte en redan använd migration för att simulera en ny version.
- Instrument och tickers hör hemma i konfiguration, inte utspridda som hårdkodade UI-värden.
- Uppdatera `README.md` när körkommandon, miljövariabler, arkitektur eller drift förändras. `scripts/check-readme-sync.sh` validerar deploykommandona.
- Rör inte orelaterade lokala ändringar och gör inte destruktiva git-operationer.

## Säkerhet och privat data

- Committa aldrig `.env`, tokens, lösenord, privata Avanza-exporter, lokala ledgerfiler eller databaser.
- `local-data/`, `backend/data/` och lokala miljöfiler är git-ignorerade avsiktligt.
- `APP_API_TOKEN` skyddar backendens `/api/*` utom health. `BACKEND_API_TOKEN` ska matcha token i frontendens servermiljö.
- `DASHBOARD_PASSWORD` är det delade lösenordet för frontendens enkla inloggning.
- Exponera normalt endast frontendport `3000`. Backendport `8000` ska vara intern vid Compose-/privat drift.
- Logga inte hemligheter eller innehållet i privata portföljfiler i tester, felmeddelanden eller commit-diffar.

## Lokal portfölj

Portföljmodulen är valfri och aktiveras med `ENABLE_LOCAL_PORTFOLIO=1`. Importfiler ligger ägarvis under `local-data/`, exempelvis `local-data/JP_avanza/` och `local-data/Pat_avanza/`. Importen använder checkpoint/ledger för att undvika att redan behandlade transaktioner appliceras igen.

Ändringar i portföljimporten ska testas med syntetiska fixtures. Använd aldrig användarens riktiga ekonomiska data som testdata och skriv inte över lokala exporter.

## Definition of done

En ändring är klar när:

1. beteendet är implementerat i rätt lager
2. relevanta tester har lagts till eller uppdaterats och passerar
3. lint/build eller backendvalidering har körts i proportion till ändringen
4. API-typer, migrationer och dokumentation är synkroniserade där de berörs
5. inga hemligheter, privata data eller orelaterade ändringar ingår i diffen
