# Issue #12 — návrh kontraktu pro PLC programátora

**Stav: návrh k potvrzení, nikoli mapa nasazeného PLC.** Stávající DB2000 ani
řízení linky se nemění. Bez schválených offsetů, datových typů a publikovacího
postupu tento kontrakt nelze připojit k dekodéru. Současný exportér dále čte
pozorované snapshoty podle `db2000.py`.

## Požadovaná data a jejich význam

| Pole / oblast | Návrh významu | Co musí potvrdit PLC programátor |
|---|---|---|
| `schema_version`, `payload_length` | Verze a délka jednoznačně určují dekódování | Nový DB nebo zpětně kompatibilní rozšíření, přesné offsety, endianita |
| `boot_id` | Nová identita při každém restartu, i po ztrátě napájení | Typ, generování, retence, záruka neopakování |
| `heartbeat` | Čítač pravidelně inkrementovaný PLC programem | Perioda, typ, přetečení, chování STOP/RUN a maximální tolerance |
| `publish_version` | Ochrana konzistence celé publikované struktury | Atomická šířka zápisu, pořadí zápisů, čtení a paměťové záruky CPU |
| `produced_total` | Kumulativní počet hotových boxů, přednostně ULInt | Přesné místo započtení, retence, reset epoch, chování při reworku |
| `oldest_seq`, `latest_seq`, `capacity` | Rozsah dostupného kruhového bufferu | Zda je buffer globální nebo pro každé BR, pořadí přepisu a prázdný stav |
| Záznam události | `boot_id`, `seq`, BR, BoxID, výsledek, směr, čas, platnost | Typy, maximální délky, výsledek patřící ke konkrétnímu BoxID |
| `timestamp_quality` | Rozlišuje synchronizovaný UTC čas od nedůvěryhodného času | Zdroj času, synchronizace, změna času a diagnostika |

Sekvence identifikuje **událost**, nikoli BoxID. Dva průjezdy stejného BoxID
musí mít dvě sekvence. Změna výsledku musí mít předem určený význam:
nová událost, nebo revize původní transakce. Nedokončený záznam se nesmí tvářit
jako potvrzený průjezd. Nulový/neplatný čas nelze vydávat za čas události.

## Konzistence a detekce ztrát

Možný postup je seqlock: PLC označí publikaci lichou verzí, zapíše obsah a
potvrdí sudou verzí. Čtenář přijme obsah jen při stejné sudé verzi před a po
čtení. **Použitelnost musí potvrdit dodavatel pro konkrétní CPU a velikost
přenosu**; samotné pojmenování pole atomicitu nezajišťuje. Alternativou je
potvrzený dvojitý buffer s jednoznačným přepnutím aktivní banky. Reader musí
mít omezený počet opakování; neúspěch znamená neplatná data, nikoli poslední
hodnotu vydávanou za aktuální.

Pro každou potvrzenou instanci bufferu se uchovává poslední přijaté `(boot_id,
seq)`. Stejná dvojice je duplikát. Jestliže očekávaná sekvence už leží před
`oldest_seq`, vznikl ztracený interval. Po změně `boot_id` se řetězec nepřipojuje
k předchozímu běhu jako spojitá historie. Při prvním spuštění čtenáře je historie
před nejstarší dostupnou událostí neznámá. Přetečení sekvence musí mít výslovný
protokol; nelze ho zaměnit za zpětné pořadí.

Kapacita musí pokrýt nejvyšší rychlost událostí krát schválenou dobu výpadku
plus rezervu. PLC buffer bez potvrzení odběru nemůže garantovat libovolně
 dlouhý výpadek. Při překročení kapacity má zaručit **detekci ztráty**, nikoli
předstíranou úplnost. Exportér do PLC nezapisuje potvrzení bez samostatně
schváleného protokolu. Zpracované sekvence musí být trvale uloženy společně
s událostmi, aby restart exportéru nevytvořil falešné duplicity nebo mezery.

## Akceptační scénáře pro budoucí implementaci

Následující scénáře jsou zadání testu, nikoli tvrzení o provedení na PLC.

| Vstup | Očekávaný výsledek |
|---|---|
| Stejný BoxID dvakrát, sekvence 41 a 42 | Dvě potvrzené události |
| Mezi čteními vzniknou sekvence 43–47, všechny v bufferu | Export všech pěti v pořadí |
| Opakované přečtení stejného bufferu | Žádné nové události ani přírůstky |
| Čtenář očekává 48, nejstarší je 53 | Výslovná mezera 48–52, nejméně 5 chybějících událostí |
| Změna obsahu uprostřed čtení | Odmítnout nekonzistentní snapshot |
| PLC restartuje a sekvence se vrátí na začátek | Nový `boot_id`, oddělená historie |
| Exportér restartuje po zápisu události | Obnovit checkpoint bez dvojího započtení |
| Přetečení/reset počítadla nebo sekvence | Zpracovat dle schválené epochy, bez falešného velkého přírůstku |
| Heartbeat stojí, TCP/Snap7 stále odpovídá | Samostatně označit PLC program jako nepotvrzený/neaktuální |
| Nesynchronizovaný PLC čas | Zachovat pořadí sekvencí, označit nejistý čas |
| Výpadek delší než kapacita bufferu | Detekovaná ztráta, žádné tvrzení o garantovaných průjezdech |

## Podklady potřebné k dokončení

Aktuální export DB, typ/firmware CPU, schválená tabulka offsetů, maximální tok
událostí, přípustná délka výpadku, definice započtení boxu, vyjádření k atomicitě
a výsledky řízených scénářů. Dokud chybí, #12 zůstává otevřená.
