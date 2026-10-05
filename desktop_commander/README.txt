DESKTOP COMMANDER REMOTE - PORTABLE WINDOWS x64

CIL:
Na firemnim PC bez admin prav nic neinstalovat.

POSTUP:
1. Stahni Desktop-Commander-Portable-win-x64.zip z GitHub Release
   "Desktop Commander Portable - latest".
2. Rozbal ZIP primo na C:\
   Vznikne C:\desktop_commander
3. Prvni autorizaci proved pres C:\desktop_commander\start.bat.
4. Po sparovani pro bezny provoz pouzivej C:\desktop_commander\start-hidden.vbs.
5. Hidden start nema viditelne CMD/PowerShell okno a loguje do logs\desktop-commander.log.

Nic se neinstaluje do Windows:
- vlastni Node.js je uvnitr slozky
- Desktop Commander a jeho zavislosti jsou uvnitr slozky
- neni potreba npm, npx, PATH ani administrator

STARTY:
start.bat        - viditelny start pro prvni OAuth a diagnostiku
start-hidden.vbs - skryty provozni start po sparovani

DALSI SOUBORY:
check.bat  - overi portable runtime bez prihlaseni
debug.bat  - spusti Remote Device s podrobnym logem
logout.bat - odstrani lokalne ulozene prihlaseni

Pri dalsim startu se autorizace standardne znovu nepýta, protoze Desktop
Commander uklada session do profilu aktualniho Windows uzivatele.

MOZNE FIREMNI BLOKACE:
Pokud start.bat nebo node.exe zablokuje AppLocker/WDAC, nebo sit blokuje
mcp.desktopcommander.app, nepomuze instalace. Je potreba povoleni IT.
Portable balicek neobchazi bezpecnostni pravidla Windows ani firemni site.

ZDROJ:
Official package @wonderwhy-er/desktop-commander
https://github.com/wonderwhy-er/DesktopCommanderMCP
