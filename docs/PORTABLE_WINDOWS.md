# Portable Windows nasazení bez admin práv

Toto je primární způsob nasazení PLC exportéru na PC v hale.

Výsledkem GitHub Actions je jeden soubor:

`PLC-export-portable-win-x64.zip`

Po rozbalení funguje samostatně. Na cílovém PC není potřeba instalovat Python,
Node.js, Git, pip, službu Windows ani měnit PATH nebo ExecutionPolicy.

## Proč je nový balík menší

Původní provozní složka z dubna 2026 používala stejný princip: embeddable Python,
lokální knihovny, `prometheus.exe` a `start.bat`. Runtime ale nebyl uložený
v Git historii; v repozitáři byl jen zdrojový kód. Proto jej pozdější běžný
deployment návod nenacházel.

Nový build zachovává původní portable model a dále jej zmenšuje:

- žádné `.venv` vedle druhé kopie Pythonu,
- Python 3.12 embeddable místo plné instalace,
- odstraněná runtime závislost na pandas/numpy,
- pouze potřebné runtime knihovny Flask, python-snap7, openpyxl a xlrd,
- z distribuce Promethea se přebírá jen `prometheus.exe` + licence,
- žádné testy, Git metadata, dokumentace ani Grafana JSON v runtime ZIPu,
- ZIP neobsahuje žádnou historickou TSDB databázi,
- lokální Prometheus je při spuštění omezen na 30 dní nebo 512 MB
  (první dosažený limit vyhrává).

CI hlídá, aby výsledný ZIP nepřekročil 180 MiB.

## Obsah po rozbalení

```text
PLC-export\
├── Python\
│   ├── python.exe
│   └── Lib\site-packages\
├── prometheus\
│   ├── prometheus.exe
│   ├── prometheus.yml
│   └── data\
├── var\
├── akl\
├── dataExcelImport\
├── gebhardt\
├── ranpak\
├── smartlog\
├── teleskop\
├── templates\
├── exporter.py
├── start-hidden.vbs
├── start.bat
├── stop.bat
├── check.bat
├── config.cmd.example
└── VERSION.txt
```

## Stažení — doporučená cesta

V repozitáři otevři **Releases → PLC Exporter Portable - latest** a stáhni
`PLC-export-portable-win-x64.zip`.

Release `portable-latest` se při každém úspěšném buildu větve `main`
automaticky nahradí aktuálním ověřeným balíkem. Vedle ZIPu je vždy
`SHA256SUMS.txt`.

Alternativně je stejný build dostupný i přes
**Actions → Portable Windows bundle → poslední zelený run → Artifacts**.

## Bezpečné přepnutí na PC v hale

Starou složku nemaž. Novou nejprve rozbal vedle ní:

```text
C:\plc_exporter          <- stará instalace
C:\plc_exporter_new      <- nový portable build
```

Pokud jsou PLC IP a cesta k plánu stejné jako současné defaulty, není třeba nic
nastavovat. Pro odlišnosti zkopíruj `config.cmd.example` jako `config.cmd`
a uprav pouze potřebné řádky.

Před přepnutím spusť v nové složce:

```text
check.bat
```

Importní část kontroly musí skončit `IMPORT OK`. Kontrola portů přirozeně
selže, dokud nový exporter ještě neběží.

Pak zastav starou instanci jejím původním způsobem a ověř, že porty 8000 a 9090
nejsou obsazené. Novou instanci běžně spustíš dvojklikem:

```text
start-hidden.vbs
```

Tento launcher schová CMD/PowerShell okna a spustí PLC Exporter i Prometheus bez
konzolových oken na hlavním panelu. Startovací výstup je uložen v
`var\startup.log`.

Pro diagnostiku lze stále použít viditelný:

```text
start.bat
```

Po startu znovu spusť:

```text
check.bat
```

Pro zastavení pouze procesů z této portable složky použij:

```text
stop.bat
```

## Přesun na finální cestu

Po ověření lze starou složku přejmenovat například na
`C:\plc_exporter_backup_20261005` a novou na:

```text
C:\plc_exporter
```

Všechny cesty uvnitř balíku jsou relativní, takže přejmenování nebo přesun celé
složky nevyžaduje reinstalaci.

## Lokální konfigurace

`config.cmd` není součástí repozitáře ani build artefaktu. Je určený pouze pro
konkrétní PC. Příklad:

```bat
set "PLC_IP=10.40.36.2"
set "PLC_DB_NUMBER=2000"
set "PLC_DB_SIZE=8122"
set "PLC_START_OFFSET=0"
set "KPI_EXCEL_PATH=I:\Bor\11-Operative\02-ZooRoyal\07-Key Account Rewe Digital\Kapa Planung"
set "PROM_RETENTION_TIME=30d"
set "PROM_RETENTION_SIZE=512MB"
```

Pokud `config.cmd` neexistuje, aplikace použije svoje současné provozní
defaulty.

## Build lokálně na jiném Windows PC

Pokud je potřeba balík vytvořit mimo GitHub Actions, na Windows PC s Pythonem
3.12 a internetem lze z checkoutu spustit:

```powershell
powershell -NoProfile -File .\scripts\build_portable.ps1
```

Výsledek bude v `dist\PLC-export-portable-win-x64.zip`.
