# Publika Avanza-fondkurser

## Mål

Hämta aktuell fondkurs från Avanzas publika webbsidor utan inloggning och använd den för att värdera fondandelar i `Min Avanza`.

Detta ska minska skillnaden mellan dashboardens värde och Avanzas aktuella fondvärde. Transaktionsfilerna fortsätter vara den enda löpande inputen för antal, köp, sälj och inköpsvärde.

## Avgränsning

- Ingen inloggning, cookie, BankID eller annan hemlighet används eller sparas.
- Aktier med direktkurs fortsätter använda Yahoo Finance och eventuell valutaomräkning.
- Bankkontot fortsätter uppdateras från transaktionsfilen.
- `local-data/` förblir ignorerad av Git.
- Om en fondkurs inte kan hämtas behålls senast kända värde, med en tydlig stale-status.

## Fas 1: Teknisk undersökning - klar 19 juni 2026

1. Installera Playwright och Chromium i backendmiljön.
2. Skapa ett litet lokalt testskript som öppnar Avanzas publika fondlista för DNB Global Indeks S.
3. Vänta på att JavaScript har laddat fondraden och läs ut:
   - fondnamn
   - ISIN
   - aktuell fondkurs eller NAV
   - tidpunkt, om den visas
4. Verifiera att den hämtade kursen kan multipliceras med `557,2517` andelar och ger ett rimligt värde jämfört med Avanza.
5. Dokumentera vilka CSS-selectorer eller vilket sidinnehåll som är stabilt nog att läsa.

### Resultat

- Playwright 1.54.0 och Chromium är installerade i backendmiljön.
- Den publika DNB-söksidan laddar utan inloggning och renderar `DNB Global Indeks S`.
- Ett reproducerbart prov finns i `scripts/probe_avanza_fund.py`.
- Sidan behöver inte läsas med CSS-selectorer för värdering. Den använder ett publikt JSON-svar med fondnamn, ISIN, NAV, NAV-datum och valuta.
- Den 19 juni 2026 var DNB:s NAV `171,77157 SEK` från `2026-06-17`. Med `557,2517` andelar blir värdet `95 720,00 kr`.

## Fas 2: Undersök Avanzas publika dataanrop - klar 19 juni 2026

1. Använd Playwrights nätverkslogg under laddningen av DNB-fonden.
2. Identifiera fetch/XHR-anrop som innehåller fondens data eller ISIN `NO0010827280`.
3. Kontrollera om ett sådant anrop fungerar utan inloggning och innehåller kurs, datum och fondidentitet.
4. Jämför alternativen:
   - Använda det publika dataanropet direkt: snabbare och mindre resurskrävande.
   - Läsa den färdigrenderade sidan med Playwright: enklare om dataanropet är internt eller föränderligt.
5. Välj metod först efter att DNB-provet är verifierat.

### Resultat och val

- Avanzas webbläsare gör ett oautentiserat `POST` till `/_api/fund-guide/list?shouldCheckFundExcludedFromPromotion=true`.
- En JSON-body med fondens namn som `name` returnerar en `fundListViews`-post med korrekt ISIN, `nav`, `navDate`, `currencyCode` och `orderbookId`.
- Samma `POST` fungerar direkt med `curl`, utan browser, cookies eller inloggning.
- Värderingen ska därför i fas 4 använda det publika JSON-anropet direkt. Playwright behålls som ett lokalt felsökningsverktyg om Avanza ändrar anropet eller svarets struktur.

## Fas 3: Lokal mappning - hoppas över

1. Utöka den lokala `ticker-map.yaml` per ägare med en fondkälla per ISIN.
2. Håll Avanza-adresser och selektorer lokala i `local-data/`.
3. Starta med:
   - DNB Global Indeks S (`NO0010827280`)
   - Avanza Emerging Markets (`SE0012454338`)
   - Avanza Zero (`SE0001718388`)
   - AMF Aktiefond Småbolag (`SE0001185000`)
4. Validera alltid att fondnamn och ISIN från sidan stämmer före kursen används.

### Beslut

ISIN finns redan i innehavet och verifieras mot Avanzas svar. Ingen lokal fondmappning behövs för den normala vägen. En lokal undantagsmappning kan läggas till senare endast för en fond som inte går att hitta automatiskt.

## Fas 4: Värdering och cache - klar 19 juni 2026

1. Lägg till en fondkurs-tjänst i backend med kurs, källa, hämtningstid och stale-status.
2. Värdera en mappad fond som `antal andelar * aktuell fondkurs`.
3. Cacha fondkurser i 12-24 timmar, eftersom fond-NAV normalt uppdateras högst en gång per handelsdag.
4. Spara senast lyckade fondkurs lokalt så att tillfälliga fel inte nollställer värdet.
5. Låt fondkurs från Avanza ersätta startsaldots värde, men ändra aldrig antal eller GAV utan transaktionsfil.

### Resultat

- Backend hämtar NAV med ISIN-validering från Avanzas publika fond-API.
- Fonder värderas som `antal andelar * NAV`, även när innehavet är sammanslaget för JP och Pat.
- Kurser sparas lokalt i `local-data/fund-prices.json` i 20 timmar. Filen ligger under den redan ignorerade `local-data/`-mappen.
- Vid ett tillfälligt fel används senast sparade NAV. API:t markerar då värderingen som stale och den valda innehavsvyn visar `Fondkurs: senast kända`.
- Ledgerns antal, inköpsvärden och bankkonto ändras inte av fondkursuppdateringen.

## Fas 5: Tester och verifiering

1. Enhetstesta parsning med sparade, anonymiserade sid- eller API-svar.
2. Testa att DNB:s andelar ger rätt värde vid en given fondkurs.
3. Testa cache, stale-fallback och fel från Avanza.
4. Jämför dashboardens värden manuellt med Avanza för JP och Pat efter första körningen.
5. Kontrollera att inga lokala exporter, värden eller inloggningsuppgifter hamnar i Git.

## Accepteranskriterier

- DNB Global Indeks S kan läsas från en publik Avanza-källa utan inloggning.
- Felaktig eller saknad fonddata påverkar inte övriga innehav.
- Aktuell fondkurs förbättrar portföljvärdet utan att ändra ledgerns antal eller inköpsvärde.
- DNB-provet har en dokumenterad och reproducerbar metod innan fler fonder läggs till.

## Infört: källor per innehav

Införandet är klart. Antal, GAV och inköpsvärde kommer alltid från den lokala transaktions-ledgern. Värderingskälla och grafkälla är separata: en proxy används bara för grafen och får aldrig ändra innehavets värde.

| Innehav | Värdering nu | Graf | Övrigt |
| --- | --- | --- | --- |
| DNB Global Indeks S | Avanza publikt NAV | ACWI via Yahoo Finance | Fond |
| Investor B | Yahoo Finance `INVE-B.ST` | Samma | Aktie |
| AMF Aktiefond Asien Stilla havet | Avanza publikt NAV | AAXJ via Yahoo Finance | Fond |
| Uranium Energy | Yahoo Finance `UEC` och USD/SEK från Yahoo Finance | Samma | Aktie i USD |
| Avanza Emerging Markets | Avanza publikt NAV | EEM via Yahoo Finance | Fond |
| WisdomTree Physical Swiss Gold | Senast kända värde från ledger/startfil | SGLD.L via Yahoo Finance | Certifikat; grafkurs ändrar inte värdet |
| Avanza Zero | Avanza publikt NAV | OMX Stockholm via Yahoo Finance | Fond |
| Avanza Tech Solutions by Barrett | Avanza publikt NAV | IXN via Yahoo Finance | Fond |
| Lundin Mining | Yahoo Finance `LUMI.ST` | Samma | Aktie |
| Viscaria | Yahoo Finance `VISC.ST` | Samma | Aktie |
| Avanza Global | Avanza publikt NAV | URTH via Yahoo Finance | Fond |
| AMF Aktiefond Småbolag | Avanza publikt NAV | OMX Stockholm Benchmark GI via Yahoo Finance | Fond |
| Bankkonto | Transaktions-ledgern | Ingen graf | Insättningar, ränta och skatt uppdaterar saldot |

Fonders NAV hämtas anonymt från Avanzas publika fond-API, utan inloggning, och cachas lokalt i 20 timmar. Om Avanza tillfälligt inte svarar används den senast kända kursen och innehavet markeras med `Fondkurs: senast kända`.
