# Dashboard, archiv a nasazení

## Import do Grafany

1. Nasaďte exportér a nastavte Prometheus scrape `/metrics`, doporučeně každých
   10 s. Pro jednu linku používejte jednu instanci exportéru a dedikovaný job
   `plc-export`. Ověřte `up=1`, `plc_data_valid=1` a `line_br_data_valid=1`.
2. Přes **Dashboards → New → Import** nahrajte `grafana/line-overview.json`
   a `grafana/machine-detail.json`. Jde o classic JSON schema 39 a nativní panely
   stat, table, timeseries, state-timeline a bargauge. Import do konkrétní
   instalace Grafany je součástí provozního ověření, nikoli CI.
3. Vyberte Prometheus datasource, job a jedinou instanci. V nastavení dashboardu → Variables nastavte skrytou proměnnou
   **history_url** na skutečnou adresu exportéru končící `/history`.
   Při přechodu na detail přes kartu zařízení ověřte tuto adresu i v detailu.
4. Karta zařízení otevře jeho detail se stejným časovým oknem. Rozložení karet
   není schéma fyzického toku. Časové osy používají Europe/Prague.
5. Ověřte řízené změny stavů a výpadek sběru s provozem. Neplatná PLC data se
   zobrazí jako neznámá; výpadek endpointu vytvoří mezeru. Potvrzení chodu není
   odvozováno z pouhé připravenosti stroje.

Plnění plánu se zobrazí jen pro dnešní platný kladný plán a platný nezáporný
PLC počet. Fallback na starší plán zůstává v exportéru kvůli kompatibilitě,
ale nový panel jej nepoužije. Výkon za 5 minut vyžaduje alespoň 90 %
pozorovaného časového pokrytí. Prometheus `increase` je extrapolovaný odhad,
proto krátká okna a řídké scrape nejsou přesný výpis archivovaných událostí.
Forecast do konce směny není implementován bez schváleného kalendáře směn,
přestávek a správné definice dokončeného boxu.

Generátor: `python scripts/build_dashboards.py`. Generované JSON jsou verzované;
testy ověřují shodu s generátorem a parsují všechny panelové PromQL výrazy.

## Lokální historie

Exportér spouští nezávislé zapisovací vlákno. `EVENT_DB_PATH` určuje SQLite
soubor, výchozí `var/observations.sqlite3`. Adresář musí být trvalý a zapisovatelný
účtem služby. SQLite používá WAL; více exportérů nesmí sdílet jeden soubor.
Ukládají se změny BR, signálů a strojních stavů, nespojitosti a zjištěné mezery.
Po startu jsou stavy označeny jako snapshot, nikoli jako nově vzniklá porucha.
Čas je čas pozorování exportéru, nikoli PLC timestamp.

- `/history`: přesné hledání BoxID nebo všech událostí v intervalu; vstup času UTC.
- `/api/events?box_id=10000001&since=2026-09-25T00:00:00Z&limit=200`:
  stejné čtení v JSON. `since`/`until` přijímají epoch nebo ISO8601; bez timezone
  se použije UTC. Výchozí období je posledních 24 hodin, nejvýše 200 řádků.
- `limit_reached=true` znamená možný další výsledek. Zužte interval; API není
  export celého archivu. Pole `completeness=observations_only` platí vždy.
- Retence je nejvýše 7 dní a 100 000 nejnověji vložených pozorování. Úklid
  probíhá při zápisu. Limit řádků není přesný limit velikosti souboru na disku;
  SQLite uvolněné stránky znovu používá. Pro zálohu použijte SQLite backup API.
- Fronta má 5 000 položek plus nejvýše 200 v opakované dávce. Zápis na disk
  neblokuje PLC. Při plné frontě jsou další záznamy zahozeny a metrika zvýšena.
  Při chybě disku se dávka opakuje; při náhlém ukončení může zmizet obsah RAM.
- `event_journal_healthy`, `pending`, `errors_total`, `dropped_total` a
  `written_total` umožňují kontrolu archivu. Čítače se resetují restartem;
  již zapsané záznamy zůstávají. Každý běh má vlastní session ID.

Historie obsahuje BoxID a ShippingLabel. Existující Flask endpoint nemá
přihlášení: provozujte jej pouze v důvěryhodné síti za řízeným přístupem či
ověřovacím reverse proxy; port nevystavujte veřejně. Nové metriky tyto
identifikátory neobsahují. Pro staré detailní metriky nastavte
`EXPORT_EVENT_DETAILS=0`, pokud je staré dashboardy již nepotřebují.

## Alerty a provozní kontrola

`prometheus_rules/smartlog.rules.yml` je JSON kompatibilní s YAML. Přidejte ho
v Prometheu do `rule_files` a upravte job v pravidle nedostupnosti podle svého
scrape configu. Ostatní pravidla se vážou na metriky exportéru; shoda
`job,instance` předpokládá standardní jediný scrape target bez dalších replik.
Při odstranění targetu z konfigurace nelze jeho absenci zjistit pomocí `up==0`;
pro pevný seznam očekávaných linek doplňte vlastní kontrolu přítomnosti.

Pravidla zahrnují nedostupnost exportéru, neplatná PLC/BR data, chybu a ztráty
archivu, nedostatek materiálu a informativní reset počítadla. Půlnoční reset
není automaticky porucha. Směrování notifikací a prahy potvrzuje provoz.
Pravidla se sama neinstalují a neodesílají zprávy.

Před nasazením spusťte testy a `promtool check rules` na cílové verzi Promethea.
Po nasazení ověřte zápis archivu, dohledání známého testovacího BoxID, všechny
BR hlavičky, skutečné ESTOP názvy a polaritu, dnešní plán, neplatný vzorek a
obnovení komunikace. Nasazení ani ověření na živém PLC tento commit neprovádí.
Rollback: vraťte předchozí commit/konfiguraci a staré dashboardy; soubor SQLite
ponechte pro analýzu. Opravené ESTOP metriky nejsou kompatibilní s původními
sekvenčně číslovanými názvy — migrační tabulka je v `DB2000.md`.

Zdroje formátů:
- https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/view-dashboard-json-model/
- https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/

## Kompaktní provozní rozložení

Přehled navazuje na uživatelův stávající dashboard z fotografií: Hlavní KPI,
Výkon a čekání v čase, Aktuální signály strojů, Stavy a materiálové události,
BR / Plausicheck a kvalita sběru. Horní KPI jsou vysoké jen tři gridové řádky;
bez celoplošných stavových barev. Počty používají celé hodnoty s oddělovačem
místo zkrácení na K. Detail a tabulky používají provozní názvy bez technických
sloupců job/instance/Time/__name__.

Signálové panely jsou v šesti čitelných sloupcích a používají původní exportované bity, vždy s kontrolou
`up` a `plc_data_valid`. Pozitivní provozní signál je zelený při 1, neaktivní
šedý; chybový signál je červený při 1. Varování je oranžové, bypass fialový.
Neaktivní chybové bity mají stav „Ne“, nejde o důkaz běhu celého zařízení.
Nové panelové odkazy z Ranpak/AKL vedou na detail a zachovávají i adresu historie.

OEE a predikce směny jsou záměrně prázdné s textem „Není definováno“ a vysvětlením
v popisu panelu. Nedostupnost výpočtu se neinterpretuje jako nula. „Pokrytí dat“
není dostupnost linky. Součet čekání stanic není sjednocený prostoj linky.
Žádný parametr délky směny/přestávky nepředstíráme, dokud není zapojen do
ověřeného výpočtu. Grafana UI import/render byl při vývoji ověřen v 11.6.0
proti Prometheu 3.2.1 se simulovanými vzorky; živé PLC se tím neověřuje.
