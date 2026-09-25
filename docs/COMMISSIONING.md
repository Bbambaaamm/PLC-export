# Issue #14 — ověření nasazení a akceptační protokol

## Co lze automaticky ověřit

Kontrolní skript přečte dvakrát **přímý `/metrics` jedné instance exportéru**.
Nezapisuje do PLC, nemění služby a nepřistupuje k boxové historii. Ověří růst
poll čítače a času posledního čtení, platnost všech 7 BR, dostupnost čtyř
prefixových čítačů, všech waiting/stavových řad a správných identifikátorů
ESTOP, dnešní kladný plán a zdraví archivu. Nevyžaduje výrobu ani neaktivní
ESTOP; kontroluje dostupnost hodnot, nikoli bezpečnost nebo provoz stroje.

Spustit z checkoutu na počítači, který má oprávněný přístup k exportéru:

```sh
python -m pip install -r requirements-dev.txt
python scripts/check_deployment.py --metrics-url http://ADRESA_EXPORTERU:8000/metrics --output deployment-report.json
```

`ADRESA_EXPORTERU` nahraďte skutečnou adresou. Skript žádný server nehledá.
Pro jiné nakonfigurované stáří PLC vzorků nastavte `--max-age` (sekundy),
pro pomalejší polling `--interval` (výchozí 5 s, nejvýše 30 s). Prodleva musí
být dost dlouhá na další čtení. HTTP timeout má výchozí 5 s. Během měření
nerestartovat exportér; reset znamená neúspěch a požadavek nového měření.

Má-li reverzní proxy bearer ověření, token předat prostředím
`PLC_CHECK_BEARER_TOKEN`, nikoli argumentem/URL. Token vyžaduje HTTPS,
certifikát se ověřuje a přesměrování se odmítá. Do reportu se neukládají URL,
hlavičky ani raw hodnoty/labely s BoxID. Snapshoty samy mohou obsahovat staré
osobní/provozní detailní řady; necommitovat je do veřejného repozitáře.

Offline varianta ze dvou dříve uložených scrape:

```sh
python scripts/check_deployment.py --first prvni.prom --second druhy.prom --output deployment-report.json
```

Výstup obsahuje jednotlivé kontroly `pass/fail/warn`; chybějící, duplicitní
nebo NaN metrika kontrolou neprojde. Návratový kód 0 znamená automatické
kontroly bez `fail` (může obsahovat varování); 1 znamená neúspěch. V obou
případech zůstává `acceptance_status=pending_manual_verification`. Offline
snapshoty nedokazují aktuální dostupnost. Růst poll čítače nepotvrzuje běh PLC
programu; k tomu je potřeba heartbeat z #12. Dva scrape neprokazují dlouhodobou
stabilitu ani úplnost historie. Report uvádí zbývající ruční kroky.

## Pořadí nasazení

1. Zapsat provozní server, dosavadní commit a konfiguraci, verze Python/Grafana/
   Prometheus a aktuální export DB. Exportovat původní dashboardy. Uchovat
   zálohu SQLite pomocí online backup API, ne kopírováním živého souboru bez WAL.
2. Potvrdit mapu všech sedmi BR, délku DB >= 7077 B, hlavičky STRING, význam
   waiting a polaritu ESTOP; migrovat staré sekvenční názvy ESTOP podle DB2000.md.
3. Nasadit konkrétní ověřený commit do jedné instance služby. Zaznamenat přesný
   příkaz restartu dané služby; název služby ani OS není v repozitáři potvrzen.
4. Spustit tento kontrolní skript, ověřit scrape target `up=1` v Prometheu,
   alerty přes `promtool check rules prometheus_rules/smartlog.rules.yml` na
   cílové verzi a provozem schválené směrování. `up` se nekontroluje z přímého
   `/metrics`, protože jej vytváří Prometheus.
5. Importovat `grafana/line-overview.json` a `grafana/machine-detail.json`;
   nastavit datasource, jediný job/instance a `history_url`. Ověřit odkazy,
   čas Europe/Prague, hodinovou produkci i filtry intervalů událostí. První
   hodina může být bez produkčního výpočtu kvůli pokrytí dat.
6. Ověřit řízené scénáře níže a uložit protokol. Prohlídka simulovaného dashboardu
   nenahrazuje potvrzení fyzických vstupů a skutečného nasazení.
7. Při závadě vrátit zaznamenaný předchozí commit/konfiguraci a původní dashboardy,
   restartovat stejnou službu a znovu ověřit sběr. SQLite ponechat pro analýzu;
   obnova staré zálohy je samostatný krok s dopadem na novější historii.

## Protokol (vyplnit pro skutečné nasazení)

Server / služba: **nedoloženo**. Nasazený commit: **nedoloženo**.
Původní rollback commit: **nedoloženo**. Aktuální DB export/verze: **nedoloženo**.
Datum, odpovědný technik, verze Grafany/Promethea: **nedoloženo**.
Automatický report: **nedoloženo**. Doba sledování: **nedoloženo**.

| Scénář | Požadovaný důkaz | Výsledek |
|---|---|---|
| Běžný chod | Dva scrape, všechny BR/stavy, data odpovídají provozu | neprovedeno |
| Známý box | Dohledaný BoxID a očekávané BR pořadí dle potvrzené mapy | neprovedeno |
| Čekání / materiál / chyba | Odpovídající bit, časová oblast a stav v Grafaně | neprovedeno |
| ESTOP | Správné místo/identifikátor/polarita dle dohodnutého postupu technika | neprovedeno |
| Ztráta a návrat spojení | Neznámý interval, žádné falešné provozní doby | neprovedeno |
| Neplatný BR STRING | Vadná BR data nejsou vydávána za platné boxy | neprovedeno |
| Reset nebo přetečení počítadla | Nespojitost, žádný falešný výrobní přírůstek | neprovedeno |
| Chybějící/dnešní plán | Správná platnost Excelu a absence neplatného plnění plánu | neprovedeno |
| Restart služby | Archiv přežije, procesové čítače se resetují bez falešného výkonu | neprovedeno |
| Záloha a obnova na kopii | Kontrola SQLite a dohledání referenčního záznamu | neprovedeno |
| Přístup k historii | Jen zamýšlení uživatelé přes potvrzené řízení přístupu | neprovedeno |
| Alerty / obnova | Skutečná pravidla načtena, prahy a příjemci potvrzeni provozem | neprovedeno |

Řízené poruchy a testy bezpečnostních vstupů provádí odpovědný technik podle
schváleného postupu. Malformované DB vzorky testovat nejprve v simulátoru;
kontrolní skript nic do PLC nevkládá. Issue #14 zůstává otevřená do doložení
skutečných výsledků.
