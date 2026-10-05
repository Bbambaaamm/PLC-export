PLC EXPORTER - PORTABLE WINDOWS x64

1. Rozbal celou slozku PLC-export napriklad jako C:\plc_exporter.
2. Nic neinstaluj. Neni potreba admin, systemovy Python ani PATH.
3. Dvojklik na start.bat.
4. Kontrola: check.bat.
5. Zastaveni pouze teto instance: stop.bat.

Python i vsechny runtime knihovny jsou ve slozce Python.
Prometheus je ve slozce prometheus a uklada data do prometheus\data.
Vychozi limity Prometheus dat jsou 30 dni / 512 MB; prvni dosazeny limit vyhrava.
Pro lokalni odlisnosti zkopiruj config.cmd.example jako config.cmd a uprav jen hodnoty.

Soubor VERSION.txt obsahuje commit a verze pouzite pri sestaveni.
