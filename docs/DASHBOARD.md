# Dashboard, archiv a nasazení

## Import do Grafany

1. Nasaďte exportér a nastavte Prometheus scrape `/metrics`, doporučeně každých
   10 s. Pro jednu linku používejte jednu instanci exportéru a dedikovaný job
   `plc_exporter`. Ověřte `up=1`, `plc_data_valid=1` a `line_br_data_valid=1`.
2. Přes **Dashboards → New → Import** nahrajte tři dashboardy: `grafana/line-overview.json`
   (čistý provozní overview), `grafana/technical-diagnostics.json` (detailní PLC/servisní
   diagnostika) a `grafana/machine-detail.json` (drill-down jednoho zařízení). Jde o classic
   JSON schema 39 a pouze nativní panely Grafany; nejsou potřeba externí pluginy. Import do
   konkrétní instalace Grafany je součástí provozního ověření, nikoli CI.
3. Dashboard je pro toto nasazení omezen na Prometheus datasource pojmenovaný **Zoo** (datasource proměnná má name filter `/^Zoo$/`). Vyberte job `plc_exporter` a jedinou instanci. Jednohodnotové proměnné `job`, `instance` a `station` se v PromQL používají přes přesnou shodu `=`, nikoli regex `=~`; tím se zabrání neplatnému escapování adres typu `127.0.0.1:8000`. V nastavení dashboardu → Variables nastavte skrytou proměnnou
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

## Profesionální provozní layout

Hlavní dashboard je záměrně rozdělen na rozhodovací vrstvu a technickou diagnostiku.
Horní řada obsahuje jen KPI, která mají význam pro okamžité řízení linky: denní počet,
5min tempo, BR08 za posledních 60 minut, počet aktivních čekání, počet kritických stavů
a platnost PLC dat. OEE a predikce směny nejsou v overview zobrazovány, dokud nemají
schválenou provozní definici.

Graf **Produkce · BR08 za posledních 60 minut** zobrazuje pět křivek: **Celkem, Boxy 05,
10, 15, 20**. Každý bod používá `increase(br08_prefix_total[1h])`, tedy klouzavý
přírůstek za předchozích 60 minut. Celkem je součet právě těchto čtyř prefixů. Zdroj je
původní čítač BR08 s deduplikací BoxID v paměti exportéru; nejde o záruku zachycení
každého fyzického průjezdu.

Incidenty již nejsou kreslené jako husté barevné anotace přes produkční křivky. Přímo
pod hlavním grafem je časově zarovnaný panel **Provozní stav zařízení**, takže společný
kurzor ukazuje, co se na jednotlivých stanicích dělo ve stejném okamžiku, ale produkční
graf zůstává čitelný. Stavové barvy jsou konzistentní: zelená = připraveno/chod, oranžová
= čekání nebo varování, červená = stop/chyba/bezpečnost, fialová = bypass, šedá = neaktivní
nebo neznámý stav.

Nouzová tlačítka používají kompaktní stavovou matici: u každého okruhu se zobrazuje pouze
název a barevný bod. Zelený bod znamená neaktivní E-STOP, červený aktivní E-STOP a šedý
neplatná data. Detailní provozní bity Ranpak/AKL/Smartlog/Teleskop byly přesunuty do
`technical-diagnostics.json`, kde mají stejný kompaktní status-dot design místo dlouhých
dekorativních barů.

Hodinový BR08 graf vyžaduje alespoň 95 % pokrytí v daném hodinovém okně a platné BR08
vzorky. Po startu nemusí být hodinu dostupný. Při zastavení klesá hodinový součet postupně,
jak starší boxy opouštějí okno. Proto zůstává samostatný 5min graf tempa ze senzoru před
vraty 38; jde o jiný měřicí bod a jiné časové okno.


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

## Rozdělení dashboardů

- **Smartlog · provozní přehled** — KPI, hlavní produkce, časově zarovnaný stav zařízení,
  kompaktní karty zařízení, bezpečnost, výkon/čekání a kvalita sběru.
- **Smartlog · technická diagnostika** — detailní PLC signály, E-STOP okruhy, materiálové
  stavy, BR/Plausicheck a integrita sběru.
- **Smartlog · detail zařízení** — drill-down vybrané stanice se stavem, čekáním,
  materiálovými signály a časem podle prioritního stavu.

Overview používá minimum dekorativních prvků a konzistentní semantické barvy. Neaktivní
stav je šedý, nikoli modrý. Diagnostické informace nejsou odstraněny; pouze jsou přesunuty
z hlavního provozního pohledu do specializovaného dashboardu.
