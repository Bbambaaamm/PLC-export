# PLC exportér

Read-only sběr DB přes Snap7 a export metrik na `/metrics` (port 8000).
Spouštěcí bod je `python exporter.py`: jedno PLC vlákno, jedno Excel vlákno
a HTTP obsluha. Samotný import Flask aplikace PLC ani Excel sběr nespustí.

## Instalace a ověření

Python 3.10–3.12; přímé závislosti jsou ve `requirements.txt`.

```sh
python -m venv .venv
# Aktivujte prostředí podle svého OS.
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python exporter.py
```

Testy simulují DB i selhání zdrojů a nepřipojují se k PLC. GitHub Actions
spouští stejnou sadu pro Python 3.10 a 3.12. Před nasazením ověřte Snap7,
mapu DB a přístup služby k plánovacímu souboru ve skutečném prostředí.

## Konfigurace prostředím

| Proměnná | Význam |
|---|---|
| `PLC_IP` | Adresa PLC; při nasazení ji nastavte explicitně. |
| `PLC_DB_NUMBER` | DB, výchozí 2000. |
| `PLC_START_OFFSET` | Musí být 0: dekodéry používají absolutní offsety DB. |
| `PLC_DB_SIZE` | Výchozí 8122 B, nejméně 3651 B. Odpověď musí přesně odpovídat nakonfigurované velikosti. |
| `PLC_READ_INTERVAL_SEC` | Pauza po čtení, výchozí 0,5 s. |
| `PLC_RECONNECT_DELAY_SEC` | Pauza po chybě, výchozí 2 s. |
| `PLC_MAX_SAMPLE_GAP_SEC` | Největší platná mezera mezi vzorky; výchozí maximum z 5 s a trojnásobku čtecího intervalu. |
| `KPI_EXCEL_PATH` | Soubor nebo složka s plánem. Nastavte cestu dostupnou účtu služby. |
| `EXCEL_REFRESH_INTERVAL_SEC` | Pauza po každém pokusu o načtení Excelu, výchozí 300 s. |
| `EXPORT_EVENT_DETAILS` | `1` zachová původní detailní řady `br08_info` a `prostoje_info`; `0` je vypne a ponechá agregace. |
| `LOG_LEVEL` | Výchozí INFO. |

Zachovány jsou původní síťové výchozí hodnoty kvůli kompatibilitě.
Repozitář obsahuje interní adresu a cestu; odstranění z historie či změna
viditelnosti repozitáře vyžadují samostatnou změnu. HTTP endpoint nemá
autentizaci a poslouchá na všech rozhraních; síťový přístup řeší hostitel.

## Platnost dat a mezery v měření

- `plc_data_valid = 1` vyžaduje úplné úspěšné čtení a stáří do
  `PLC_MAX_SAMPLE_GAP_SEC`. Při chybě je 0 ihned, při zastaveném čtení
  vyprší při scrape. Poslední stavové hodnoty zůstávají dostupné;
  dashboard je musí vyhodnocovat společně s platností dat.
- `plc_last_read_timestamp`, `plc_data_staleness_seconds`,
  `plc_read_errors_total` a `plc_poll_total` umožňují kontrolu sběru.
- Doby chyb se integrují monotónním časem podle předchozího vzorku.
  Chyba komunikace nebo příliš dlouhá mezera přeruší časovou kontinuitu.
  Neznámý interval se nepřičítá jako porucha ani jako prokázaný provoz.
- Otevřená prostojová událost se při přerušení zahodí. Pokud po obnovení
  prostoj trvá, začne nový měřený úsek. Součty dokončených událostí tedy
  neobsahují neúplný úsek před výpadkem. Kratší prostoje než 10 s se nadále
  ignorují; méně než 120 s je typ `mikro`, ostatní `standard`.
- Čítače jsou v paměti a při restartu se resetují. Pro Prometheus použijte
  `rate`/`increase`; nejde o trvalý archiv událostí. Události kratší než
  vzorkovací perioda nebo vzniklé při výpadku sběru nejsou garantované.

## Plán a kompatibilita Grafany

- Úspěšný reload nahradí celý plán, včetně změněných a odstraněných dnů.
  Selhání ponechá poslední plán, nastaví `excel_data_valid = 0` a zvýší
  `excel_read_errors_total`. Poslední úspěch je
  `excel_last_reload_timestamp`. Pomalu načítaný Excel neblokuje PLC.
- `target_pocet_boxu` bez labelu zůstává aktuální plán; pokud dnešek chybí,
  zůstává původní fallback na poslední dostupný den do dneška. Datum je
  viditelné v `target_pocet_boxu_aktivni_info`.
- `target_pocet_boxu_podle_dne{datum="YYYY-MM-DD"}` publikuje snapshot
  celého plánu. Původní alias `target_pocet_boxu{datum="..."}` je zachován.
  Obě řady používají čas scrape, nikoli explicitní historický timestamp.
  Datum plánu filtrujte labelem; time picker zobrazuje historii pozorovaných
  snapshotů a neimportuje zpětně historické hodnoty Excelu do Promethea.
- Časové a stavové čítače `*_total` mají správně typ `counter`.
- `exporter_pending_queue_fill_ratio{queue="pending_excel"}` je odstraněn:
  Excel již nepoužívá omezenou frontu. Obě událostní fronty zůstávají.
- Agregace událostí probíhá při příjmu, takže zaplnění 500prvkové fronty
  neztratí počty ani dokončené doby. Detailní historie zůstává omezená.
  Kvůli vysoké kardinalitě doporučujeme po úpravě dashboardů přepnout
  `EXPORT_EVENT_DETAILS=0`. Bez přepnutí zůstává původní riziko růstu řad.

## Význam KPI vyžadující provozní rozhodnutí

BR08 zachovává dosavadní potlačení opakovaného BoxID se stejným výsledkem.
`line_br08_events_total` zahrnuje i změny kódu/směru, není automaticky
počtem unikátních fyzických průjezdů. Přesná identifikace opakovaného průjezdu
vyžaduje kontrakt s PLC (např. sekvenční číslo nebo potvrzení události).

`line_prostoje_duration_seconds_total` je součet časů jednotlivých stanic,
nikoli sjednocená doba zastavení linky. Paralelní prostoje se sčítají.
Pro OEE celé linky je potřeba definovat rozhodující signál/provozní stav;
tento součet nepoužívejte přímo jako nedostupnost linky.

## Nasazení a návrat

Před změnou zaznamenejte nasazený commit, prostředí a dotazy Grafany.
Nejprve spusťte testy, potom restartujte jednu instanci exportéru s původní
konfigurací. Ověřte `/metrics`, `plc_data_valid`, aktualizaci PLC timestampu,
Excel health a plán. Ověřte i chování při řízeně simulovaném výpadku zdroje.
Při návratu nasaďte předchozí commit a jeho prostředí; restart v obou směrech
resetuje procesové čítače. Tento PR sám neprovádí nasazení ani zápis do PLC.
