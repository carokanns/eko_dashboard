# Min Avanza Lokalt

## Summary
Bygg en lokal-only avdelning **“Min Avanza”** i befintlig dashboard. V1 utgår
från en Avanza-export med aktuella innehav och visar varje papper ungefär som
**Mag 7**: kort, vald graf och bildspel. Grafen visar instrumentets pris-/
kursutveckling där datakälla finns, medan text visar ditt **nuvarande
innehavsvärde** och **inköpsvärde**. Ingen historik över ditt eget
portföljvärde i v1.

## Key Changes
- Skapa lokal datamapp `local-data/avanza/` och git-ignorera `local-data/` så
Avanza-filer inte versionshanteras eller råkar hamna i GitHub.
- Håll all Avanza-inloggning och alla hemligheter helt utanför Git/GitHub.
  - Ingen kod, dokumentation, config, testdata eller README i repo ska innehålla
  credentials, tokens, sessioner, personliga länkar eller detaljerade
  instruktioner för hur man loggar in på ditt Avanza.
  - Om inloggning eller hämtning direkt från Avanza någonsin blir en funktion
  ska den hanteras som separat lokal-only design med hemligheter i lokala
  env-filer/secret storage som är git-ignorerade.
- Lägg till strikt lokal feature gate:
  - Backend exponerar portfölj-API endast när instansen startas med lokal
  env-flagga, t.ex. `ENABLE_LOCAL_PORTFOLIO=1`.
  - Frontend visar **“Min Avanza”** endast när backend bekräftar att funktionen
  är aktiv.
  - Publik Render/Vercel-deploy ska inte kunna visa fliken eller nå
  portföljendpointen eftersom flaggan och lokala data saknas där.
- Läs Avanza CSV/Excel från `local-data/avanza/`.
  - Importera aktuella innehav: namn, antal/andelar, nuvarande värde,
  inköpsvärde och eventuell ISIN/ticker.
  - Läs nuvärde och inköpsvärde direkt från exporten i v1.
- Lägg till lokal ticker-/datakällemappning:
  - Aktier/ETF:er som kan mappas till Yahoo Finance får automatiska grafer.
  - Fonder kräver separat fonddatakälla/mappning; i v1 visas de alltid med
  värden, och får graf bara om stabil historik går att hämta.
- Lägg till lokalt portfolio-API:
  - sammanfattning med innehav, antal/andelar, nuvärde, inköpsvärde och
  totaler
  - serie per mappat papper med samma range-val som marknadsgraferna
- Lägg till frontend-tabben **“Min Avanza”**:
  - total nuvarande portföljvärde
  - KPI-kort per innehav
  - vald graf med pris-/kurshistorik
  - text i grafpanelen: nuvarande värde och inköpsvärde
  - bildspelsslides för portföljpapper som har grafdata

## Later
- När du exporterar/lämnar nya transaktioner kan appen räkna om antal/andelar
och inköpsvärde.
- Historiskt värde av din egen portfölj tas som separat senare steg, baserat
på transaktioner eller lokala snapshots.
- Din frus Avanza kan läggas till som separat lokal portfölj när din egen
fungerar.

## Test Plan
- Backend:
  - portfolio-endpoints är avstängda när lokal flagga saknas.
  - portfolio-endpoints fungerar när `ENABLE_LOCAL_PORTFOLIO=1` och lokal
  testfil finns.
  - parser hanterar Avanza-export med innehavsvärde och inköpsvärde.
  - omappade papper/fonder visas utan graf men finns kvar i sammanfattningen.
- Frontend:
  - **“Min Avanza”** visas inte utan lokal aktivering.
  - fliken visas när appen körs med aktiv backend-flagga och lokal testdata.
  - kort, vald graf och bildspel följer Mag 7-mönstret.
  - grafpanelen visar nuvarande värde och inköpsvärde som text.
  - saknad grafdata kraschar inte sidan.
- Kör backendtester, frontend `npm test`, `npm run lint` och `npm run build`.

## Assumptions
- V1 använder Avanza-export för nuvarande värde och inköpsvärde.
- V1 räknar inte historiskt portföljvärde eller historiskt värde av ditt eget
innehav.
- V1 börjar med automatiska grafer för papper som kan mappas till befintlig
eller stabil datakälla.
- Funktionen ska bara vara aktiv i en lokalt startad instans med uttrycklig
env-flagga och lokal data. Den behöver inte blockera LAN, Tailscale, TeamViewer,
RustDesk eller åtkomst från en annan egen dator, så länge datan hålls utanför
Git/GitHub och publik deploy inte har flaggan eller data.
