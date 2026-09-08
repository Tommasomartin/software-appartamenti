# Versione web (pagina singola)

`prospetto-lotti-fab.html` è la dashboard in **un solo file**, che gira interamente nel
browser: nessun server, nessuna installazione. È la versione pubblicata come Artifact.

Pubblicata qui: <https://claude.ai/code/artifact/341a1975-7704-4cd7-aa32-782c749dda64>

Si può anche aprire in locale con un doppio clic sul file.

## Cosa contiene

Stesso motore di calcolo della versione Python, riscritto in JavaScript:
scala FAB con intermediazione, costi di acquisto, IMU calibrata per zona, oneri di
mantenimento a 3/6/12 mesi, comparabili di zona, rivendita con i due metodi, semaforo.

I dataset di riferimento sono incorporati nella pagina: vengono rigenerati da
`app/data/*.json` con lo script qui sotto, così le due versioni non divergono.

```bash
python scripts/genera_dati_web.py
```

## Differenze rispetto alla versione locale

| | Pagina web | Applicazione locale |
|---|---|---|
| Installazione | nessuna | `./avvia.sh` |
| Excel e CSV | sì | sì |
| PDF | no | sì |
| Archivio dei pool caricati | no (una sessione) | sì, database locale |
| Esportazione | CSV | Excel con foglio delle ipotesi |
| Import quotazioni OMI ufficiali | no | sì |
| Comparabili propri da CSV | no | sì |

I file caricati non lasciano il browser in nessuna delle due versioni.
