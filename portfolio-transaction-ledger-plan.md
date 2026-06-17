# Transaktionsstyrd Lokal Avanza-Förteckning

## Summary

Bygg om Min Avanza så appen har en egen lokal masterförteckning över JP och Pats innehav: antal aktier, antal fondandelar och banktillgodo. `positioner` och `konto` används bara för engångs-seed när masterfilen saknas. Därefter är transaktionsfilen den enda Avanza-inputen som uppdaterar förteckningen vid uppstart.

## Key Changes

- Skapa en ignorerad lokal masterfil, t.ex. `local-data/portfolio-ledger.json`, med:
  - JP/Pat ägare i fast ordning.
  - Innehav per ägare och instrument: ISIN, namn, antal, anskaffningsvärde, GAV, ticker/proxy-metadata.
  - Banktillgodo per ägare.
  - Processade transaktioner som normaliserade row-hashar per ägare, så samma fil kan läsas om utan dubbelbokning.
  - Seed-metadata: vilka `positioner`/`konto`-filer som användes första gången.

- Engångs-seed:
  - Om masterfil saknas, bygg den från senaste `*positioner*.csv` och `*konto*.csv`.
  - Spara befintliga innehav, antal, GAV/anskaffningsvärde, ticker/proxy och bankkonto.
  - Markera befintlig transaktionsfil som baseline så historiska rader inte dubbelappliceras ovanpå seedat nuläge.
  - Efter att masterfilen finns ska `positioner` och `konto` inte användas automatiskt längre.

- Transaktionsuppdatering vid uppstart:
  - Vid backend-start: läs senaste `*transaktion*.csv` / `*transaction*.csv` för JP och Pat.
  - Identifiera nya rader via normaliserad row-hash.
  - Applicera bara nya transaktioner på masterfilen.
  - Hantera `Köp`, `Sälj`, `Autogiroinsättning`, `Inlåningsränta`, `Preliminärskatt kapitalränta`, `Utdelning` och `Intern överföring`.
  - Banktillgodo uppdateras bara för konto `Bank` / sparkonto-liknande bankkonto i v1.
  - Köp av nytt instrument skapar nytt innehav även om det saknas i seed.
  - Ticker gissas best-effort med befintlig logik; om det inte går visas innehavet utan graf och flaggas som saknad mapping.

- Värdering:
  - Antal och banktillgodo kommer från masterfilen.
  - Aktier med fungerande direkt-ticker värderas med Yahoo/marknadsdata där det är säkert.
  - Fonder/proxy-instrument värderas i v1 till anskaffningsvärde efter transaktioner; proxy används fortsatt för graf när mapping finns.
  - Totalerna i API/UI byggs från masterfilen, inte från `positioner`/`konto`.

- API/UI:
  - `portfolio/summary` ska läsa masterförteckningen och returnera samma shape som idag, plus metadata om ledger-status och eventuella saknade mappings.
  - Sammanställningssliden visar JP/Pat enligt masterfilen: innehavsvärde, inköpsvärde, resultat, bankkonto och totalt inkl. bankkonto.
  - Enskilda innehavsslides fortsätter visa total instrumentrad plus JP/Pat-uppdelning.
  - `portfolio/status` är enabled om masterfil finns, eller om nödvändiga seedfiler finns för att skapa den.

## Test Plan

- Seed:
  - Masterfil skapas från JP/Pat positioner + konto när den saknas.
  - Seedade transaktionsrader dubbelappliceras inte.
  - JP och Pat behåller korrekt ägarordning.

- Transaktioner:
  - Nytt köp ökar antal och anskaffningsvärde.
  - Sälj minskar antal och reducerar anskaffningsvärde med genomsnittlig kostnad.
  - Nytt instrument från köp skapas automatiskt.
  - Bank-insättning, ränta och skatt på `Bank` uppdaterar banktillgodo.
  - Intern överföring påverkar banktillgodo enligt `Belopp` när kontot är `Bank`.
  - Oförändrad transaktionsfil ger 0 nya rader vid nästa uppstart.

- API/UI:
  - Summary använder masterfilen även om `positioner`/`konto` ändras efter seed.
  - Saknad ticker visas utan graf och med mapping-varning.
  - Bildspelets sammanställningsslide visar bankkonto och total inkl. bankkonto.
  - Frontend build och befintliga portfolio/slideshow-tester passerar.

## Assumptions

- `positioner` och `konto` är tillåtna endast för första seed eller framtida explicit manuell reseed.
- Transaktionsfilen är komplett från seed-tidpunkten och framåt.
- V1 visar bara bankkonto/sparkonto som banktillgodo, inte eventuell likvid på ISK/aktie-fondkonto.
- Fonder utan exakt prisfeed värderas till anskaffningsvärde tills vidare.
- Masterfilen och all Avanza-data ligger under `local-data/` och ska aldrig versioneras.
