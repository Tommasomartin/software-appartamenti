# Prospetto Immobili

Dashboard per analizzare pool immobiliari acquistati da fondi: carichi il file dei lotti
(Excel, CSV o PDF) e ottieni in **una sola schermata** il prezzo di acquisto scontato per
classe FAB, tutti i costi, il valore di rivendita stimato sui comparabili di zona e il
semaforo delle opportunità.

---

## Avvio in 30 secondi

```bash
./avvia.sh                 # macOS / Linux
avvia.bat                  # Windows
```

Lo script installa le dipendenze e apre il browser su `http://127.0.0.1:8000`.

Se preferisci fare a mano:

```bash
pip install -r requirements.txt
python avvia.py
```

Poi clicca **Carica file pool** e seleziona il tuo file. Per una prova immediata:

```bash
python scripts/genera_esempio.py     # crea samples/pool_esempio.xlsx
```

---

## Cosa fa

### 1. Legge il tuo file, comunque sia fatto

Formati: `.xlsx` `.xlsm` `.xls` `.csv` `.tsv` `.pdf`.

Non serve preparare il file. Il sistema:

- individua da solo la riga di intestazione, anche sotto righe di titolo del fondo;
- riconosce le colonne dai nomi italiani più diffusi (`Prezzo base d'asta`, `Sup. commerciale mq`,
  `Stato occupativo`, `Prov.`, `Rendita catastale`, …);
- capisce i numeri all'italiana (`1.250.000,50`) e all'inglese (`1,250,000.50`);
- trova il codice **FAB** in una colonna dedicata oppure dentro il testo del lotto (`Lotto FAB-07`);
- classifica la tipologia dalla descrizione o dalla categoria catastale
  (residenziale, ufficio, ricettivo, capannone, commerciale, box, terreno);
- riconosce **libero / occupato / occupato senza titolo** e **sano / da ristrutturare / da rifare**;
- scarta i fogli di servizio (legende, note) e i PDF senza tabelle li legge a espressioni regolari.

Se una colonna viene letta male, la correggi dalla scheda dell'immobile e il prospetto si
ricalcola subito.

### 2. Applica lo sconto FAB

La classe FAB determina **quanto paghiamo del prezzo scritto nel file**. FAB basso = più
sconto, FAB alto = meno sconto. Valori di partenza, tutti modificabili dal pannello *Ipotesi*:

| FAB | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Paghiamo | 30% | 30% | 35% | 40% | 45% | 50% | 55% | 60% | 65% | 70% |

### 3. Calcola tutti i costi

**Acquisto** — imposta di registro 2% (acquisto da fondo), imposte ipotecaria e catastale,
notaio a scaglioni con IVA e spese, provvigione agenzia 2%, due diligence, perizia, visure,
e la ristrutturazione stimata al mq secondo lo stato di conservazione letto dal file.

**Mantenimento — più tieni l'immobile, più ti costa.** Il costo è mostrato a **3, 6 e 12 mesi**
e su qualunque orizzonte scegli in alto (fino a 36 mesi):

- **IMU calibrata sulla zona**: se il file contiene la rendita catastale il calcolo è esatto
  (`rendita × 1,05 × moltiplicatore catastale × aliquota comunale`); altrimenti la rendita
  viene stimata dai mq con i parametri della fascia del Comune. Le aliquote sono quelle
  ordinarie per regione, con override per i 20 Comuni maggiori;
- condominio, TARI (solo se occupato), assicurazione, manutenzione, utenze — tutti in €/mq/anno
  per tipologia, riscalati con un moltiplicatore regionale;
- se l'immobile è **occupato** il canone viene sottratto, al netto di gestione e rischio sfitto.

**Rivendita** — provvigione agenzia 2% sul prezzo finale, marketing, APE e pratiche, e
opzionalmente la tassazione sulla plusvalenza.

### 4. Stima il prezzo di rivendita sui comparabili di zona

Per ogni immobile trovi il **€/mq di zona negli ultimi 3, 6 e 12 mesi**, l'intervallo
min–max della zona e la variazione annua del mercato.

Il valore lordo viene poi rettificato con coefficienti espliciti (li vedi tutti nella scheda):
stato di conservazione, stato di occupazione, piano, liquidità della tipologia e sconto medio
in trattativa. Il prezzo di uscita è quindi normalmente **più basso** del valore di mercato
teorico.

I **terreni** hanno un modello dedicato: un terreno edificabile non vale i suoi mq al prezzo
del costruito, vale l'area edificabile che esprime
(`valore residenziale × incidenza area × indice di edificabilità`). L'indice si legge dal file
o si imposta a mano; è il parametro che pesa di più e il sistema te lo segnala.
I terreni agricoli usano valori medi regionali.

### 5. Ti dice dove guardare per primo

Ogni immobile riceve un **semaforo**:

- 🟢 **verde** — multiplo ≥ 2,0x, ROI ≥ 60% e utile ≥ 30.000 €
- 🟡 **giallo** — multiplo ≥ 1,35x, ROI ≥ 25% e utile ≥ 8.000 €
- 🔴 **rosso** — sotto le soglie, o in perdita

Le soglie sono modificabili. Un immobile verde viene **declassato** se è occupato senza titolo
o se i dati letti dal file sono troppo incompleti: la colonna **Dati** mostra la confidenza
del prospetto, così sai quando il numero è solido e quando va verificato.

Il **multiplo** è quello che chiedevi: investo 50, incasso 150 → 3,00x.

### 6. Mappe e verifiche

Dalla scheda di ogni immobile: **Google Maps**, **Google Earth**, vista **Satellite**,
**Street View** e **Quotazioni OMI**. Con latitudine e longitudine nel file i link puntano
esattamente sul punto; altrimenti cercano l'indirizzo. Le coordinate si possono aggiungere a mano.

### 7. Esporta

Il pulsante **Esporta Excel** produce un file con 41 colonne — tutte le voci di costo, i
comparabili 3/6/12 mesi, i link alle mappe e le motivazioni del semaforo — più un foglio
`Ipotesi` con i parametri usati per quel calcolo.

---

## I dati di mercato: leggi questo prima di offrire

I valori di mercato inclusi sono una **baseline interna** (`app/data/mercato.json`), costruita
su ordini di grandezza pubblici. Servono a far girare il sistema da subito, **non sono un dato
certificato** e non bastano per decidere un acquisto.

Per lavorare su dati reali hai due strade:

**A. Quotazioni OMI ufficiali** (Agenzia delle Entrate, la fonte pubblica più autorevole):

```bash
# scarica il file da https://www1.agenziaentrate.gov.it/servizi/geopoi_omi/index.php
python scripts/importa_omi.py QI_20261_VALORI.zip
```

**B. I tuoi comparabili.** Scarica il modello CSV da *Fonti dati → Scarica modello CSV*,
compilalo con le tue rilevazioni e ricaricalo. I tuoi dati hanno sempre la precedenza.

Allo stesso modo, le aliquote IMU di default vanno verificate sulla delibera del Comune:
ogni Comune fissa la propria e può cambiarla ogni anno.

---

## Struttura del progetto

```
app/
  main.py              avvio applicazione
  api.py               endpoint HTTP
  models.py            schema canonico Immobile e Prospetto
  storage.py           persistenza SQLite
  config.py            percorsi e caricamento dataset
  ingest/
    mapping.py         riconoscimento colonne e parser dei valori
    excel.py           lettura Excel/CSV con header automatico
    pdf.py             estrazione tabelle da PDF
    normalizza.py      righe grezze -> Immobile
  engine/
    valutazione.py     prospetto economico completo
    costi.py           notaio, imposte, IMU, oneri, capex
    comparabili.py     valori di mercato per zona e periodo
    punteggio.py       semaforo, punteggio, confidenza
    geo.py             link Maps / Earth / OMI
  data/                dataset di riferimento (JSON, modificabili)
  static/              dashboard (HTML, CSS, JS - nessun build)
scripts/
  genera_esempio.py    crea un pool di prova
  importa_omi.py       importa le quotazioni OMI ufficiali
tests/                 79 test su motore e API
```

I dati che carichi restano sul tuo computer: `portafoglio.db` e `uploads/` non escono mai
dalla macchina e non sono tracciati da git.

## Test

```bash
python -m pytest tests/ -q
```

## Personalizzare i parametri

Quasi tutto si regola dal pannello **Ipotesi** senza toccare il codice: scala FAB, percentuali
di imposte e provvigioni, costi fissi, sconto in trattativa, soglie del semaforo, tassazione
della plusvalenza.

I dataset più profondi sono file JSON in `app/data/`:

| File | Contenuto |
|---|---|
| `mercato.json` | €/mq per provincia, rapporti fra tipologie, trend, coefficienti di rettifica |
| `imu_oneri.json` | aliquote IMU, moltiplicatori catastali, oneri €/mq/anno, costi di ristrutturazione |
| `geografia.json` | 107 province italiane con regione |
| `ipotesi_default.json` | valori di partenza del pannello Ipotesi |
