# Champ Converter

Piccola applicazione web in italiano per trasformare screenshot di risultati di calcio in un file Excel (.xlsx) aggiornabile ogni settimana.

## Cosa fa

- Riceve uno o più screenshot JPG, PNG o WEBP dei risultati.
- Estrae automaticamente le partite concluse mediante un modello visivo OpenAI.
- Mostra una tabella modificabile per verificare e correggere i risultati.
- Esporta **una riga per partita** e **solo sei colonne**: **Giornata · Data · Casa · Gol casa · Gol ospite · Ospite**.
- Puoi ricaricare l'Excel della settimana precedente per aggiungere la nuova giornata e aggiornare risultati già presenti senza duplicati.

La squadra **a sinistra nello screenshot è Casa**; quella **a destra è Ospite**. Il primo punteggio è Gol casa, il secondo è Gol ospite.

Esempio: 5 | 13/11/2026 | Polisportiva San Giorgio | 4 | 2 | TNT A

## Utilizzo

1. Apri l'app.
2. Se hai già un file Excel esportato, ricaricalo nel primo riquadro.
3. Carica gli screenshot. Inserisci Giornata e Data solo se non sono leggibili nelle immagini.
4. Clicca su **Leggi risultati dalle immagini**.
5. Controlla e correggi le righe proposte.
6. Clicca **Scarica Excel aggiornato** e conserva il file per la settimana successiva.

## Avvio in locale

Richiede Python 3.10+.

1. Crea e attiva un ambiente Python virtuale.
2. Esegui `pip install -r requirements.txt`.
3. Esegui `streamlit run app.py`.
4. Inserisci la chiave OpenAI nella barra laterale dell'app, oppure imposta la variabile di ambiente `OPENAI_API_KEY`.

## Pubblicazione web

GitHub ospita il codice, **non avvia da solo l'app Python**. Per renderla utilizzabile dal browser, collega questa repository a [Streamlit Community Cloud](https://share.streamlit.io/), specificando `app.py` come main file e configurando `OPENAI_API_KEY` nei Secrets dell'app.

## Costi, dati e affidabilità

Il riconoscimento delle immagini usa l'API OpenAI, con **costi separati dall'abbonamento ChatGPT**. Gli screenshot sono inviati all'API per l'analisi; controlla sempre l'anteprima prima dell'esportazione. **Non inserire mai chiavi API nella repository GitHub**.

L'app non conserva i risultati in un database: il file Excel scaricato è la copia da ricaricare ogni settimana. Supporta la modifica manuale delle partite. Le date esportate sono vere date Excel e i punteggi sono numerici.

## File

- `app.py`: interfaccia Streamlit
- `vision.py`: lettura automatica delle immagini
- `models.py`: normalizzazione, controlli e deduplicazione
- `excel_io.py`: import/export Excel
- `requirements.txt`: dipendenze
- `tests/test_core.py`: test di base

Per eseguire i test: `python -m unittest discover -s tests -v`.

**Nota:** l'app è stata testata sulla trasformazione dei dati e sull'Excel; il riconoscimento su screenshot reali va verificato con immagini del campionato.