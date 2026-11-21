"""Champ Converter — screenshot risultati di calcio -> Excel aggiornabile."""
from __future__ import annotations

import hashlib
import os
from datetime import date

import streamlit as st

from excel_io import export_xlsx, import_xlsx
from models import HEADERS, canonical, merge_rows, sort_rows, validate
from vision import extract_matches

st.set_page_config(page_title="Champ Converter", page_icon="⚽", layout="wide")

st.markdown("# Champ Converter")
st.caption("Dagli screenshot dei risultati a un file Excel ordinato, aggiornabile ogni settimana.")
st.info("**Regola fissa:** squadra nella colonna a sinistra = **Casa**; squadra a destra = **Ospite**. Il primo gol appartiene alla squadra di casa.")

if "matches" not in st.session_state:
    st.session_state.matches = []
if "editor_nonce" not in st.session_state:
    st.session_state.editor_nonce = 0
if "excel_digest" not in st.session_state:
    st.session_state.excel_digest = None


def secret_key() -> str:
    value = os.environ.get("OPENAI_API_KEY", "")
    if value:
        return value
    try:
        return st.secrets.get("OPENAI_API_KEY", "")
    except (FileNotFoundError, KeyError):
        return ""


with st.sidebar:
    st.header("Impostazioni")
    api_key = secret_key()
    if api_key:
        st.success("Chiave API configurata")
    else:
        api_key = st.text_input("OpenAI API key", type="password", help="Inseriscila qui solo per questa sessione, oppure configura OPENAI_API_KEY nei Secrets di Streamlit.")
    st.caption("La lettura automatica delle immagini richiede una chiave API OpenAI con fatturazione separata da ChatGPT.")
    st.markdown("---")
    st.caption("Nessun archivio centrale: salva l'Excel scaricato e ricaricalo alla settimana successiva.")

st.markdown("### 1. Recupera il campionato già esportato (facoltativo)")
previous_file = st.file_uploader(
    "Carica l'Excel della settimana precedente",
    type=["xlsx"],
    key="previous_xlsx",
    help="I risultati nuovi saranno aggiunti al file esistente senza duplicare le partite.",
)
if previous_file is not None:
    data = previous_file.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    if st.session_state.excel_digest != digest:
        try:
            imported = import_xlsx(data)
            st.session_state.matches, _, _ = merge_rows(imported, st.session_state.matches)
            st.session_state.excel_digest = digest
            st.session_state.editor_nonce += 1
            st.success(f"Importate {len(imported)} partite dal file precedente.")
        except Exception as exc:
            st.error(f"Impossibile leggere l'Excel: {exc}")

st.markdown("### 2. Carica le immagini dei risultati")
col_round, col_date = st.columns(2)
with col_round:
    fallback_round = st.number_input(
        "Giornata (se non appare nello screenshot)", min_value=0, max_value=99,
        value=0, step=1, help="Lascia 0 se la giornata è visibile nell'immagine."
    )
with col_date:
    fallback_date = st.date_input(
        "Data (se non appare nello screenshot)", value=None, format="DD/MM/YYYY",
        help="Lascia vuoto se la data appare nell'immagine."
    )

uploaded_images = st.file_uploader(
    "Screenshot JPG, PNG o WEBP",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
    help="Puoi caricare più screenshot nella stessa operazione.",
)

if uploaded_images:
    with st.expander(f"Anteprima di {len(uploaded_images)} immagini"):
        for upload in uploaded_images:
            st.image(upload.getvalue(), caption=upload.name, width=550)

if st.button("Leggi risultati dalle immagini", type="primary", disabled=not uploaded_images):
    if not api_key:
        st.error("Per il riconoscimento automatico inserisci la tua OpenAI API key nella barra laterale.")
    else:
        new_matches = []
        progress = st.progress(0, text="Analisi immagini...")
        for i, upload in enumerate(uploaded_images or []):
            try:
                rows = extract_matches(
                    image_bytes=upload.getvalue(), api_key=api_key,
                    default_round=int(fallback_round) or None,
                    default_date=fallback_date.strftime("%d/%m/%Y") if isinstance(fallback_date, date) else "",
                )
                new_matches.extend(rows)
                st.write(f"**{upload.name}:** {len(rows)} partite riconosciute")
            except Exception as exc:
                st.error(f"Errore nell'immagine {upload.name}: {exc}")
            progress.progress((i + 1) / len(uploaded_images), text="Analisi immagini...")
        progress.empty()
        if new_matches:
            st.session_state.matches, added, updated = merge_rows(st.session_state.matches, new_matches)
            st.session_state.editor_nonce += 1
            st.success(f"Estrazione completata: {added} nuove partite, {updated} risultati aggiornati.")
        else:
            st.warning("Non sono state riconosciute partite concluse. Controlla le immagini oppure inserisci le righe manualmente.")

st.markdown("### 3. Verifica e correggi i risultati")
st.caption("Puoi correggere nomi, punteggi e date direttamente nella tabella, aggiungere o eliminare righe. Gli screenshot vanno sempre verificati.")

blank_row = {"Giornata": None, "Data": "", "Casa": "", "Gol casa": None, "Gol ospite": None, "Ospite": ""}
editor_data = st.session_state.matches if st.session_state.matches else [blank_row]

edited = st.data_editor(
    editor_data,
    key=f"matches_editor_{st.session_state.editor_nonce}",
    num_rows="dynamic",
    hide_index=True,
    use_container_width=True,
    column_order=list(HEADERS),
    column_config={
        "Giornata": st.column_config.NumberColumn("Giornata", min_value=1, max_value=99, step=1, format="%d"),
        "Data": st.column_config.TextColumn("Data", help="gg/mm/aaaa", max_chars=10),
        "Casa": st.column_config.TextColumn("Casa", width="large"),
        "Gol casa": st.column_config.NumberColumn("Gol casa", min_value=0, max_value=99, step=1, format="%d"),
        "Gol ospite": st.column_config.NumberColumn("Gol ospite", min_value=0, max_value=99, step=1, format="%d"),
        "Ospite": st.column_config.TextColumn("Ospite", width="large"),
    },
)

if hasattr(edited, "to_dict"):
    candidates = edited.to_dict("records")
else:
    candidates = list(edited)
# Ignora la riga iniziale vuota; conserva quelle parziali per le correzioni.
records = [canonical(row) for row in candidates if isinstance(row, dict) and any(
    str(row.get(h, "") if row.get(h) is not None else "").strip() for h in HEADERS
)]
issues = [(idx, validate(row)) for idx, row in enumerate(records, start=1)]
issues = [(idx, reasons) for idx, reasons in issues if reasons]
if issues:
    st.error(f"Ci sono {len(issues)} righe incomplete o non valide. Correggile prima di esportare.")
    for idx, reasons in issues[:10]:
        st.caption(f"Riga {idx}: " + "; ".join(reasons))
    if len(issues) > 10:
        st.caption("... e altre righe da correggere")
else:
    st.caption(f"{len(records)} partite pronte per l'Excel.")

left, right = st.columns([1, 3])
with left:
    if st.button("Svuota tabella"):
        st.session_state.matches = []
        st.session_state.excel_digest = None
        st.session_state.editor_nonce += 1
        st.rerun()
with right:
    if records and not issues:
        payload = export_xlsx(sort_rows(records))
        st.download_button(
            "Scarica Excel aggiornato",
            data=payload,
            file_name="champ_converter_risultati.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
    else:
        st.download_button(
            "Scarica Excel vuoto (modello)",
            data=export_xlsx([]),
            file_name="champ_converter_modello.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

st.markdown("---")
st.caption("Formato Excel: Giornata · Data · Casa · Gol casa · Gol ospite · Ospite. Le date sono vere date Excel e i gol sono numeri.")
