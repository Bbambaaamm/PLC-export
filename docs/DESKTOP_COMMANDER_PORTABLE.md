# Desktop Commander Remote — portable Windows bez admin práv

Cíl je stejný jako u PLC exportéru: na cílovém PC se nic neinstaluje.

## Použití na PC v hale

1. V repozitáři otevři **Releases → Desktop Commander Portable - latest**.
2. Stáhni `Desktop-Commander-Portable-win-x64.zip`.
3. ZIP rozbal přímo na disk `C:\`.
4. Vznikne:

```text
C:\desktop_commander\
├── node\
│   └── node.exe
├── app\
│   └── node_modules\...
├── start.bat
├── start-hidden.vbs
├── check.bat
├── debug.bat
├── logout.bat
└── VERSION.txt
```

5. První autorizaci spusť přes:

```text
C:\desktop_commander\start.bat
```

Desktop Commander otevře OAuth autorizaci v prohlížeči. Zkontroluj, že kód v
prohlížeči odpovídá kódu v terminálu, přihlas se ke správnému účtu a zařízení
potvrď.

6. Po spárování používej pro běžný provoz:

```text
C:\desktop_commander\start-hidden.vbs
```

Tento launcher nemá viditelné CMD/PowerShell okno. Aktuální běh loguje do
`logs\desktop-commander.log`; předchozí běh se zachová jako
`logs\desktop-commander.previous.log`.

Další spuštění standardně použije uloženou session v profilu Windows uživatele.

## Co se na cílovém PC neinstaluje

Balík už obsahuje:

- Node.js x64,
- `@wonderwhy-er/desktop-commander`,
- všechny jeho runtime závislosti,
- platformní ripgrep a další npm runtime soubory.

Není potřeba systémový Node.js, npm, npx, Git, změna PATH ani administrátor.

## Kontrola

Bez přihlášení lze spustit:

```text
C:\desktop_commander\check.bat
```

Kontrola ověřuje:

- portable `node.exe`,
- `desktop-commander remote --help`,
- dostupnost přibaleného ripgrep.

Skutečné spojení s Remote MCP vyžaduje síť. První autorizaci proveď přes
`start.bat`; po spárování používej `start-hidden.vbs`.

## Firemní omezení

Portable balík neobchází bezpečnostní politiku PC. Na konkrétním firemním PC
může spojení zastavit například:

- AppLocker / WDAC zákaz spuštění `node.exe`,
- proxy nebo firewall blokující `mcp.desktopcommander.app`,
- blokovaná OAuth stránka v prohlížeči.

Pokud portable `node.exe` projde a síť dovolí Remote MCP, není pro Desktop
Commander potřeba administrátorská instalace.

## Verze a supply-chain kontrola

Build pinuje konkrétní verze Node.js a Desktop Commanderu. Node ZIP se při
sestavení porovnává s oficiálním SHA256 z nodejs.org. Výsledný ZIP dostane
vlastní `SHA256SUMS.txt` a `VERSION.txt`.

Aktuální výchozí build:

- Node.js 22.23.3 x64
- `@wonderwhy-er/desktop-commander` 0.2.52

Upstream:
https://github.com/wonderwhy-er/DesktopCommanderMCP

Oficiální Remote MCP setup:
https://github.com/desktop-commander/remote-desktop-commander/blob/main/docs/SETUP.md
