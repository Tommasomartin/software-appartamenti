# Come è stata costruita la base di valutazione

Aggiornata al **9 settembre 2026**.

## File di origine

Un solo file, nessun altro:

```
C:\Users\Tommaso\Desktop\lavoro\Valutazione immobili\File immobili\file forza.xlsm
```

Foglio unico `--UNITI--`. Intestazioni alla riga 7, dati dalla riga 8 alla 129:
**122 immobili**. Colonne A–K, nessuna oltre la K. La colonna B (`Banca`) è
interamente vuota nel file.

Il vecchio file da 644 immobili non esiste più su disco e nessun suo dato è
stato usato.

## Ordine con cui viene deciso il valore di rivendita

1. **Prezzo già presente nel file** — colonna K `a quanto si vende info 09/2026`.
   Dove c'è, viene usato **esattamente quello**: non viene ricalcolato né
   sostituito. La quotazione OMI resta agganciata solo come termine di confronto.
2. **Comparabili reali di mercato** — annunci di vendita verificati su
   Immobiliare.it.
3. **Quotazione OMI** dell'Agenzia delle Entrate.
4. Se nessuna delle tre regge: **STIMA NON AFFIDABILE — DATI INSUFFICIENTI**,
   con la motivazione scritta per esteso.

Il prezzo di acquisto non entra **mai** nel calcolo del valore di rivendita.
Serve solo al costo dell'operazione e al moltiplicatore.

## Come è stata ricavata la quotazione OMI

Il servizio pubblico di consultazione OMI dell'Agenzia delle Entrate
(<https://www1.agenziaentrate.gov.it/servizi/geopoi_omi/index.htm>), semestre
**2025/2**, l'ultimo pubblicato.

Per ogni riga:

1. il comune è stato risolto nel codice catastale OMI;
2. l'indirizzo è stato geocodificato (OpenStreetMap / Nominatim);
3. il punto è stato confrontato con i **perimetri ufficiali delle zone OMI**
   scaricati in KML dall'Agenzia delle Entrate, e la zona è stata assegnata per
   inclusione geometrica del punto nel poligono — non per somiglianza di nome.
   Tutte e 122 le righe cadono dentro una zona del proprio comune;
4. dalla scheda OMI della zona si prendono minimo e massimo €/m² per la
   destinazione e la tipologia corrispondenti, stato conservativo *normale*
   quando pubblicato (scelta prudenziale), altrimenti lo stato prevalente della
   zona;
5. il valore usato è la **media fra minimo e massimo**, applicata alla
   superficie del file.

Tutte le quotazioni OMI raccolte sono riferite a **superficie lorda (L)**, la
stessa misura della colonna `Sup. Lorde`: nessuna conversione è stata applicata.

Corrispondenza fra le destinazioni del file e quelle OMI:

| File | OMI | Tipologie cercate |
|---|---|---|
| Residenziale | Residenziale | Abitazioni civili → di tipo economico → Ville e Villini |
| Commerciale | Commerciale | Negozi → Magazzini |
| Uffici | Terziaria | Uffici → Uffici strutturati |
| Logistico/Produttivo | Produttiva | Capannoni industriali → Capannoni tipici → Laboratori |
| Terreni, Altro, Ricettivo | *nessuna* | l'OMI non le copre |

## Il controllo di coerenza superficie/prezzo

Su una parte rilevante delle righe la superficie del file **non è la superficie
commerciale del fabbricato** ma l'area del lotto o l'aggregato di più unità.
Applicare un €/m² di fabbricato a quella superficie gonfia il valore di 10–30
volte.

Il programma se ne accorge così: calcola il €/m² implicito nel prezzo del file e
lo confronta con il minimo OMI della zona. Sotto il **30%** la stima per metro
quadro non viene pubblicata e la riga diventa
`STIMA NON AFFIDABILE — DATI INSUFFICIENTI`, conservando il valore teorico solo
come riferimento visibile nel dettaglio.

Il prezzo del file serve qui **solo a rilevare l'incoerenza**, mai a costruire
il valore.

Tre annunci hanno confermato la diagnosi in modo esplicito: a San Vito al Torre
i 24.609 m² del file comprendono 13.400 m² di area esterna; a Lugo i 2.162 m²
comprendono un terreno agricolo; a Santa Sofia il laboratorio è di 310 m² contro
i 1.309 del file.

## I comparabili di mercato

Cercati su Immobiliare.it. Dalla ricerca è emerso che **il portafoglio è
pubblicato in vendita** da *iQera Italia SPA* (511 annunci). Incrociando i 122
immobili del file con quegli annunci per comune, indirizzo e superficie:

- **18 immobili del file risultano essi stessi in vendita sul mercato**, con
  prezzo richiesto verificato uno per uno sull'annuncio;
- per 2 immobili non pubblicati sono stati raccolti comparabili nello stesso
  comune e nella stessa categoria.

Sui 18 verificati il prezzo richiesto sul mercato è mediamente **+20%** rispetto
all'`ASKING PRICE` del file (da 0% a +61%): l'asking del file è il prezzo di
cessione del portafoglio, l'annuncio è il prezzo al pubblico.

**I prezzi degli annunci sono prezzi richiesti, non prezzi di vendita
conclusi.** Il realizzo effettivo sarà di norma inferiore per effetto della
trattativa. Il programma li espone come tali.

## Fonti conservate

Per ogni riga il programma conserva e mostra: zona OMI e sua descrizione,
semestre, tipologia e stato conservativo usati, €/m² minimo e massimo, la
tabella OMI integrale della zona, il link alla scheda ufficiale, i comparabili
con prezzo, superficie e link all'annuncio, la motivazione della stima e gli
avvisi. Tutto finisce anche nell'esportazione CSV.

## Rigenerare i dati

`valutazioni-omi.js` è il sorgente dei dati; è incorporato dentro
`Valutazione-Immobili-FAB.html` fra i marcatori `INIZIO DATI OMI` / `FINE DATI
OMI` perché la pagina funzioni aprendola con un doppio clic, senza server.

Dopo aver modificato `valutazioni-omi.js`:

```powershell
.\dati\incorpora-dati.ps1
```

## Cosa non è stato fatto

- **Terreni agricoli ed edificabili (12 righe):** l'OMI non pubblica quotazioni
  per i terreni. Restano senza stima, salvo i due con annuncio proprio.
- **Immobili «Altro» e ricettivi:** fuori dal perimetro OMI.
- I comparabili di portale sono stati raccolti sugli immobili del portafoglio
  effettivamente pubblicati e su due casi di zona; non è stata fatta una ricerca
  di comparabili per ciascuno dei restanti immobili.
