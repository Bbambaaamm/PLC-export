# Windows v hale: připojení a nasazení

Otevři tento návod na PC v hale. U každého bloku na GitHubu použij tlačítko
kopírování vpravo nahoře a vlož celý blok do **Windows PowerShellu 5.1**.
Začni běžným účtem, bez správce. Postupuj po jednotlivých krocích.
Adresy a cesty si příkazy vyžádají; nemusíš je upravovat uvnitř kódu.

> **Primární způsob nasazení je nyní hotový portable ZIP bez instalace a bez admin práv.**
> Viz [PORTABLE_WINDOWS.md](PORTABLE_WINDOWS.md). Tento dokument ponecháváme jako
> diagnostický a ruční fallback, případně pro připojení Remote Desktop Commanderu.

**Nejkratší cesta:** kroky 1–2 připojí PC. Potom napiš do chatu
„PC v hale je připojené“ a jeho název. Další kroky můžeme provést společně.
Když připojení nepůjde, kroky 3–8 umožní ruční nasazení.

Příprava nestopuje starý exportér, nemění firewall ani oprávnění a nezapisuje
do PLC. Přepnutí probíhá až v kroku 6. Příkazy nespouštěj hromadně jako jeden skript.

## 1. Zjištění stavu PC — pouze čtení

```powershell
hostname
$PSVersionTable.PSVersion
Get-Command py,python,node,npx.cmd -ErrorAction SilentlyContinue | Select-Object Name,Source
if (Get-Command py -ErrorAction SilentlyContinue) { py --list }
if (Get-Command node -ErrorAction SilentlyContinue) { node --version }
if (Get-Command npx.cmd -ErrorAction SilentlyContinue) { npx.cmd --version }
Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,OwningProcess
Get-Process python,pythonw,prometheus,grafana,grafana-server -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,Path
```

Kontrola současného exportéru (chyba spojení pouze znamená, že na této adrese neodpovídá):

```powershell
try {
    $plcResponse = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/metrics' -TimeoutSec 10 -ErrorAction Stop
    $plcResponse.Content -split "`n" | Select-String '^(plc_data_valid|plc_poll_total|plc_data_staleness_seconds|excel_data_valid|event_journal_healthy)\s'
    Write-Host 'HTTP odpovida. Starsi exporter nemusi vsechny tyto metriky mit.'
} catch {
    Write-Host ('Exporter na portu 8000 neodpovida: ' + $_.Exception.Message)
}
```

## 2. Připojení Remote Desktop Commander

Vyžaduje Node.js **18+**, dostupné `npx.cmd`, přístup k internetu a povolené
spouštění balíčků na tomto PC. Příkaz stáhne a spustí agenta; nejde pouze o diagnostiku.
Samostatná desktopová aplikace není potřeba.

**Otevři pro agenta samostatné okno PowerShellu** a vlož:

```powershell
npx.cmd @wonderwhy-er/desktop-commander@latest remote
```

1. Pokud npm požádá o potvrzení stažení balíčku, potvrď jej.
2. V otevřeném prohlížeči se přihlas ke stejnému účtu Desktop Commanderu jako u QuantLabu.
3. Porovnej kód v terminálu s kódem v prohlížeči a potvrď **Verify Device**.
4. Vyčkej na potvrzení připraveného zařízení. Okno ponech otevřené.
5. Na [stránce zařízení](https://mcp.desktopcommander.app/) ověř nové PC.
6. Do chatu napiš název PC z kroku 1. Ověříme spojení a správný cílový počítač.

Zavření tohoto okna nebo `Ctrl+C` připojení ukončí; trvalé odebrání zařízení
je možné na stránce zařízení. Tento krok nevytváří automatické spuštění agenta.

**Pokud chybí Node.js nebo spuštění blokuje správa PC:** pošli přesnou chybu.
Samotný PowerShell Node.js nenahradí. Nepoužívej změnu ExecutionPolicy,
obcházení proxy či vypínání ochrany. Lze pokračovat ručním nasazením níže;
případnou přenosnou verzi Node.js nejprve ověřit s IT.

Oficiální postup: [Remote Desktop Commander – SETUP](https://github.com/desktop-commander/remote-desktop-commander/blob/main/docs/SETUP.md).

## 3. Stáhnout ověřený exportér do nové složky

V dalším okně PowerShellu. Používáme konkrétní sloučenou verzi `8535f72`
(PR #17), nikoli pohyblivý ZIP hlavní větve. Git není potřeba.
Tato verze obsahuje aplikaci a dashboardy; tento později přidaný návod čti na GitHubu.

```powershell
$ErrorActionPreference = 'Stop'
$plcCommit = '8535f72478c52c63671000594eddd22e77374ca2'
$plcStage = Join-Path $env:LOCALAPPDATA ('PLC-export-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $plcStage -ErrorAction Stop | Out-Null
$plcZip = Join-Path $plcStage 'source.zip'
Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/Bbambaaamm/PLC-export/archive/$plcCommit.zip" -OutFile $plcZip
Expand-Archive -LiteralPath $plcZip -DestinationPath $plcStage
$plcProject = Join-Path $plcStage "PLC-export-$plcCommit"
Set-Location -LiteralPath $plcProject
$plcCommit | Set-Content -LiteralPath (Join-Path $plcStage 'DEPLOYED_COMMIT.txt') -Encoding ASCII
Write-Host ('Nova slozka: ' + $plcProject)
```

Pokud download selže kvůli síti nebo přihlášení, otevři
[ZIP stejné verze](https://github.com/Bbambaaamm/PLC-export/archive/8535f72478c52c63671000594eddd22e77374ca2.zip)
v prohlížeči nebo přenes soubor schváleným způsobem. Rozbal jej přes Průzkumník.
Pak nastav složku obsahující `exporter.py`:

```powershell
$plcProject = (Read-Host 'Vloz cestu ke slozce obsahujici exporter.py').Trim('"')
Set-Location -LiteralPath $plcProject
if (-not (Test-Path -LiteralPath '.\exporter.py')) { throw 'Ve slozce chybi exporter.py.' }
```

## 4. Python a závislosti — stará instalace zůstává beze změny

Použij cestu k existujícímu **python.exe verze 3.10–3.12**, kterou jsme zjistili
v kroku 1 nebo v konfiguraci současného exportéru. Chybějící `py` neznamená,
že Python není nainstalovaný. Nepoužívej bez ověření zástupce Microsoft Store.
Následující kroky vytvářejí nové prostředí pouze v nové složce.

```powershell
$ErrorActionPreference = 'Stop'
$plcPython = (Read-Host 'Vloz celou cestu k existujicimu python.exe').Trim('"')
if (-not (Test-Path -LiteralPath $plcPython -PathType Leaf)) { throw 'python.exe nebyl nalezen.' }
& $plcPython -c "import sys; print(sys.version); print('Bits:', 64 if sys.maxsize > 2**32 else 32); sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,12) else 1)"
if ($LASTEXITCODE -ne 0) { throw 'Pouzij Python 3.10 az 3.12.' }
& $plcPython -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Vytvoreni prostredi selhalo.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Instalace zavislosti selhala. Nespoustet exporter.' }
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Testy selhaly. Nespoustet exporter.' }
```

Není potřeba `Activate.ps1` ani změna ExecutionPolicy. Testy používají simulované
DB a nepřipojují se k PLC. Očekáváno **44 úspěšných testů** této verze.

### Když PC nemá přístup k Python balíčkům

Na jiném povoleném **Windows PC se stejnou verzí a architekturou Pythonu**,
ve stejné verzi projektu, připrav balíčky následujícím blokem. Tento krok
neprováděj současně s předchozí online instalací:

```powershell
$plcDownloadPython = (Read-Host 'Cesta k odpovidajicimu python.exe na pripravnem Windows PC').Trim('"')
& $plcDownloadPython -m pip download --only-binary=:all: -r requirements-dev.txt -d wheelhouse
if ($LASTEXITCODE -ne 0) { throw 'Balicky nejsou kompletni; neprovadet offline instalaci.' }
```

Přenes složku `wheelhouse` do složky projektu na PC v hale. Po vytvoření `.venv`
nahraď online instalaci tímto blokem:

```powershell
& .\.venv\Scripts\python.exe -m pip install --no-index --find-links .\wheelhouse -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Offline instalace selhala.' }
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Testy selhaly.' }
```

## 5. Nastavení skutečného PLC a plánu

Stále ve stejném okně a nové složce. Údaje převzít z existující konfigurace
a potvrzené mapy DB. Velikost DB nepřebírat naslepo. Exportér používá rack 0,
slot 1; jiná konfigurace vyžaduje úpravu a ověření.

```powershell
$env:PLC_IP = (Read-Host 'Skutecna IP adresa PLC').Trim()
$env:PLC_DB_NUMBER = (Read-Host 'Cislo databloku, obvykle 2000').Trim()
$env:PLC_DB_SIZE = (Read-Host 'Potvrzena delka cteni DB v bajtech, dosavadni default 8122').Trim()
$env:PLC_START_OFFSET = '0'
$env:KPI_EXCEL_PATH = (Read-Host 'Cesta k Excel planu nebo jeho slozce').Trim('"')
$env:EVENT_DB_PATH = Join-Path (Get-Location).Path 'var\observations.sqlite3'
if ([string]::IsNullOrWhiteSpace($env:PLC_IP)) { throw 'Chybi IP PLC.' }
if ($env:PLC_DB_NUMBER -notmatch '^\d+$') { throw 'Neplatne cislo DB.' }
if ($env:PLC_DB_SIZE -notmatch '^\d+$' -or [int]$env:PLC_DB_SIZE -lt 7077) { throw 'Delka cteni musi byt potvrzena a nejmene 7077 B.' }
if (-not (Test-Path -LiteralPath $env:KPI_EXCEL_PATH)) { throw 'Plan neni pod timto uctem dostupny.' }
New-Item -ItemType Directory -Path '.\var' -Force | Out-Null
Test-NetConnection -ComputerName $env:PLC_IP -Port 102
```

`TcpTestSucceeded=True` potvrzuje pouze TCP spojení, nikoli správnou mapu nebo
oprávnění čtení PLC. Nová složka dostane vlastní archiv; původní archiv nepřepisujeme.
Proměnné platí jen v tomto PowerShellu a jeho potomcích. Pro restart se nastavení
musí znovu zadat nebo později převést do ověřené konfigurace služby/úlohy.
Soubor `.env` aplikace automaticky nenačítá.

Staré detailní metriky necháváme ve výchozím režimu kvůli současné Grafaně.
Teprve po ověření, že je staré panely nepotřebují, lze před startem zadat:

```powershell
$env:EXPORT_EVENT_DETAILS = '0'
```

## 6. Přepnutí a první spuštění

**Před tímto krokem:** zaznamenat starou složku, příkaz spuštění, účet,
konfiguraci a způsob zastavení/obnovení. Zachovat původní Python prostředí
a export původních dashboardů. Pokud starý exportér používá SQLite, pro živou
zálohu použít SQLite backup API podle [protokolu](COMMISSIONING.md), ne prostou
kopii otevřeného databázového souboru. Novou složku nesměrovat na jeho živý archiv.

Starý exportér zastavit jeho známým způsobem; neukončovat všechny procesy Python.
Pokud jej hlídá služba nebo naplánovaná úloha, nejprve ověřit i její restartování.
Příkaz startu níže port znovu kontroluje, ale nenahrazuje kontrolu druhé instance.

```powershell
$ErrorActionPreference = 'Stop'
$plcBusy = @([System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() | Where-Object { $_.Port -eq 8000 })
if ($plcBusy.Count -gt 0) { throw 'Port 8000 je obsazeny. Nejprve vyresit starou instanci.' }
if ([string]::IsNullOrWhiteSpace($env:PLC_IP) -or [string]::IsNullOrWhiteSpace($env:KPI_EXCEL_PATH)) { throw 'V tomto okne chybi konfigurace z kroku 5.' }
& .\.venv\Scripts\python.exe exporter.py
```

Okno nech otevřené. `Ctrl+C` zastaví tuto novou instanci. Je to první zkušební
spuštění, nikoli automatická služba. Přístup k portu 8000 a historii má být
omezený na zamýšlenou interní síť; endpoint nemá vlastní přihlášení.

## 7. Ověření v dalším PowerShellu

Vlož cestu k nové složce projektu z kroku 3:

```powershell
$plcProject = (Read-Host 'Cesta k nove slozce obsahujici exporter.py').Trim('"')
Set-Location -LiteralPath $plcProject
& .\.venv\Scripts\python.exe scripts\check_deployment.py --metrics-url http://127.0.0.1:8000/metrics --output .\var\deployment-report.json
$plcCheckExit = $LASTEXITCODE
Get-Content -LiteralPath '.\var\deployment-report.json'
Write-Host ('Navratovy kod kontroly: ' + $plcCheckExit)
Start-Process 'http://127.0.0.1:8000/history'
```

`passed` znamená úspěch automatických kontrol. `failed` vyžaduje projít konkrétní
výsledky; neznamená automaticky, že nefunguje PLC (může chybět dnešní plán).
`pending_manual_verification` zůstává správně až do fyzického ověření linky.
Report neobsahuje BoxID a můžeš jej předat do chatu. Na známém boxu ověř historii,
na skutečných stavech linky BR, čekání, materiál i označení ESTOP.

## 8. Grafana a Prometheus

Otevření složky s importními soubory:

```powershell
Invoke-Item -LiteralPath (Join-Path (Get-Location).Path 'grafana')
$plcGrafanaUrl = Read-Host 'Vloz skutecnou URL vasi Grafany'
Start-Process $plcGrafanaUrl
```

1. V Prometheu ověř target exportéru `up=1`. Pokud se změnil počítač/adresa,
   upravit existující target; nepřidávat duplicitní sběr stejné instance.
2. Před importem exportuj staré dashboardy. Import stejného UID může nabídnout
   přepsání; pro souběžné porovnání zvol při importu jiné UID.
3. **Dashboards → New → Import:** `grafana/line-overview.json` a
   `grafana/machine-detail.json`. Vyber skutečný Prometheus datasource,
   správný job a jedinou instanci.
4. `history_url` nastav v obou dashboardech na adresu dosažitelnou z prohlížeče
   uživatele, například adresu PC v hale s portem 8000 a cestou `/history`.
   `localhost` funguje pouze při prohlížení na stejném PC jako exportér.
5. Ověř čas Europe/Prague. Pro hodinový graf počítej přibližně s hodinou sběru.
   „Celkem“ zde znamená součet prefixů 05/10/15/20 na BR08.

Podrobný [návod pro Grafanu, metriky a alerty](DASHBOARD.md).

## 9. Trvalé spouštění a návrat

Po úspěšném testu převést novou cestu k Pythonu, pracovní složku a všechny
proměnné do **existujícího způsobu spouštění**. Účet musí mít přístup k PLC,
plánu i zapisovatelnému archivu. Přihlašovací údaje neukládat do GitHubu.
Ponechání okna otevřeného nezajišťuje chod po odhlášení ani restartu PC.

Pomocná identifikace služby a úlohy, pouze čtení (při odepření přístupu předat IT):

```powershell
Get-CimInstance Win32_Service | Where-Object { $_.Name -match 'plc|export|python' -or $_.PathName -match 'exporter\.py|PLC-export' } | Select-Object Name,State,StartMode,StartName
Get-ScheduledTask | Where-Object { $_.TaskName -match 'plc|export|python' -or ($_.Actions.Execute -join ' ') -match 'python' -or ($_.Actions.Arguments -join ' ') -match 'exporter\.py|PLC-export' } | Select-Object TaskName,TaskPath,State
```

Prázdný výsledek nedokazuje absenci automatického startu: může být schovaný za
obecným `.bat` nebo službou. Konkrétní změnu služby/úlohy uděláme po identifikaci,
aby nevznikly dvě instance. Ověřit start po restartu v dohodnutém servisním okně.

**Návrat při problému:** zastavit novou instanci, obnovit původní spouštění,
konfiguraci a případně původní dashboardy, spustit starou instanci a ověřit sběr.
Nový archiv ponechat pro analýzu. Restart resetuje procesové čítače.

## Co poslat zpět

- Název PC, verze Pythonu/Node.js a výsledek párování.
- Cestu nové a původní instalace, způsob automatického spuštění.
- `var/deployment-report.json`, URL Grafany a výsledek targetu v Prometheu.
- Konkrétní chybu nebo snímek; neposílat hesla, tokeny ani kompletní prostředí.

Nasazení se uzavírá podle [COMMISSIONING.md](COMMISSIONING.md), nikoli pouze
úspěšným připojením Desktop Commanderu.
