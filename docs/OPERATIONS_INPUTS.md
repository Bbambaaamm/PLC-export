# Issue #13 — podklady pro schválení topologie a KPI

**Stav: chybějící provozní podklady.** Vyplnit s provozem a dodavatelem;
nepřebírat směny jiných linek ani odvozovat trasu z pořadí adres DB.
Dosavadní hodinový graf BR08 = přírůstky prefixů 05/10/15/20, nikoli
potvrzení expedice. Ready u Ranpak není potvrzený pracovní cyklus.

## Mapa toku

Přiložit schválené schéma s váhou, V10/V20, AKL pravou/levou, teleskopy T1/T2
a BR01/02/06/08/09/10/11. Pro **každou hranu** vyplnit:

| Odkud | Kam | Podmínka směrování / kód | Paralelní větev / návrat | Zdroj a schválil |
|---|---|---|---|---|
| doplnit | doplnit | doplnit | doplnit | doplnit |

Dále určit: kde vzniká BoxID, kdy se může znovu použít, jak se rozezná opakovaný
průjezd a na kterém místě se box započítá do produkce, kvality a expedice.
Rozlišit fyzickou trasu od informační návaznosti transakcí.

## ProLag / Plausicheck

| Kód | Význam dle dodavatele | Platí pro které BR | Vazba na BoxID / sekvenci | Dopad a obsluha |
|---|---|---|---|---|
| 200 | OK dle komentáře současného DB; potvrdit rozsah významu | doplnit | doplnit | doplnit |
| 4xx | Konkrétní význam není doložen | doplnit jednotlivé kódy | doplnit | doplnit |

Doložit také neznámý kód, timeout, pozdní odpověď pro minulý box a prázdnou
odpověď. Pro ShippingLabel určit formát, dobu platnosti, vazbu na transakci,
požadované shody Plausichecku a podmínku úspěšné aplikace etikety. Pouhá
přítomnost textu etikety nemůže znamenat dobrou zásilku.

## Jednoznačné definice směnových KPI

| Vstup | Co vyplnit |
|---|---|
| Hotový box | Událost/senzor, započítání reworku, duplicity a vyřazeného boxu |
| Kalendář | Europe/Prague, začátky/konce směn podle dne, výjimky a svátky |
| Noční směna | Datum přiřazení, interval `[začátek, konec)`, přechod půlnoci |
| Přestávky | Přesné intervaly, zda se odečítají z plánu; překryvy sjednotit |
| Změna času | Směny na jarní/podzimní přechod; uplynulý čas počítat z UTC okamžiků |
| Plán | Denní nebo směnový, jednotka, verze, změny v průběhu směny |
| Dostupnost | Rozhodující signál celé linky; souběh větví, blokace a nedostatek vstupu |
| Ideální takt | Sekund/box, případně podle typu; zdroj a platnost |
| Kvalita | Dobrý / zmetek / rework, měřicí bod a dostupný čítač |
| Pokrytí | Minimální přijatelné pokrytí a chování při výpadku |
| Forecast | Vstupní okno tempa, zbývající plánovaný čas, podmínky skrytí |
| Schválení | Jméno/role, datum a verze definic |

Po schválení: dostupnost = doba chodu / plánovaný výrobní čas; výkon =
ideální výrobní čas skutečného mixu / doba chodu; kvalita = dobré kusy /
všechny posouzené kusy. OEE je jejich součin jen při kompatibilních hranicích
měření a úplných vstupech. Nulový jmenovatel, neznámá kvalita či chybějící
čas nejsou nulové OEE. Neořezávat nesmyslný výkon automaticky na 100 %;
nejprve vyhodnotit takt, reset nebo nesoulad měřicích bodů.

## Ruční referenční příklady před implementací

Pro každý případ dodat vstupní události, schválené intervaly a očekávaný výsledek.

| Případ | Co musí výpočet rozlišit |
|---|---|
| Noční směna přes půlnoc + denní reset čítače | Jedna směna, žádný falešný záporný/vysoký přírůstek |
| Přestávka překrývající prostoj | Bez dvojího odečtu času |
| Dvě současně čekající stanice po 10 minut | Žádné automatické prohlášení 20 minut prostoje celé linky |
| Změna mixu 05/10/15/20 | Použití odpovídajících ideálních taktů |
| Výpadek sběru uprostřed směny | Neznámý interval oddělený od chodu i prostoje |
| Restart PLC/exportéru | Bez falešných vyrobených kusů |
| Směna při změně letního/zimního času | Skutečný uplynulý čas, jednoznačná časová pásma |
| Nulová výroba / nulový plán / chybějící kvalita | Definovaný nevyhodnotitelný stav |
| Po přestávce nebo delším zastavení | Forecast jen při platném vstupním okně a dostatečném pokrytí |

Do potvrzení těchto vstupů dashboard ponechává OEE a predikci „Není definováno“.
Issue #13 nelze uzavřít pouhým vyplněním ilustračních hodnot.
