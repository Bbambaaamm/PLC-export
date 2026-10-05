PLC EXPORTER - PORTABLE WINDOWS x64

1. Rozbal celou slozku PLC-export napriklad jako C:\plc_exporter.
2. Nic neinstaluj. Neni potreba admin, systemovy Python ani PATH.
3. Bezny start bez viditelnych CMD/PowerShell oken: dvojklik na start-hidden.vbs.
4. Kontrola: check.bat.
5. Jednorazove zapnuti chytreho autostartu: autostart-enable.bat.
6. Kontrola autostartu: autostart-status.bat.
7. Vypnuti autostartu: autostart-disable.bat.
8. Zastaveni pouze teto instance: stop.bat.

start.bat zustava jako diagnosticky start s viditelnym oknem.
start-hidden.vbs spusti stejnou logiku skryte a zapise vystup do var\startup.log.
PLC Exporter i Prometheus pak bezi bez konzolovych oken na hlavnim panelu.

CHYTRY AUTOSTART:
autostart-enable.bat nejprve zkusi Windows Task Scheduler tak, aby se PLC
Exporter spustil uz pri bootu i bez prihlaseni. Boot task bezi pod aktualnim
Windows uzivatelem, ne pod SYSTEM. Setup proto jednou pozada o Windows heslo;
heslo se neuklada do PLC-export souboru, configu ani logu.

Pokud prava nebo firemni politika boot task nepovoli, automaticky se vytvori
uzivatelsky Startup shortcut. Ten nevyzaduje admin prava a spousti exporter
skryte po prihlaseni.

Vychozi KPI cesta pouziva I:\. Pokud je I: sitovy mapovany disk, setup se ho
pokusí prevest na UNC jen pro boot rezim (config.boot.cmd), protoze mapovane
disky nejsou pred prihlasenim spolehlive dostupne.

autostart-status.bat vypise, zda je aktivni BOOT TASK, STARTUP FALLBACK nebo DISABLED.
Doporuceni: autostart zapni az po finalnim umisteni slozky C:\plc_exporter.

Python i vsechny runtime knihovny jsou ve slozce Python.
Prometheus je ve slozce prometheus a uklada data do prometheus\data.
Vychozi limity Prometheus dat jsou 30 dni / 512 MB; prvni dosazeny limit vyhrava.
Pro lokalni odlisnosti zkopiruj config.cmd.example jako config.cmd a uprav jen hodnoty.

Soubor VERSION.txt obsahuje commit a verze pouzite pri sestaveni.


GRAFANA CLOUD:
Portable balicek zna endpoint i Metrics ID pro ZooRoyal.
Token NENI v ZIPu ani v GitHubu.

Prvni nastaveni:
1. V Grafana Cloud vytvor token v access policy stack-654487-hm-write
   se scope metrics:write.
2. Dvojklik na grafana-cloud-setup.bat a token vloz do skryteho promptu.
3. Pokud Prometheus uz bezi, spust stop.bat a potom start-hidden.vbs.

Token se ulozi do:
%LOCALAPPDATA%\PLC-export\grafana-cloud.token

Tato cesta je mimo C:\plc_exporter, proto token prezije dalsi rozbaleni
noveho portable ZIPu pres C:\plc_exporter.

Cloud endpoint:
https://prometheus-prod-24-prod-eu-west-2.grafana.net/api/prom/push
Metrics ID:
1009857
