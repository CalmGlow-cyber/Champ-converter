"""Estrazione di risultati da screenshot con OpenAI Vision."""
from __future__ import annotations

import base64
import io
import json

from PIL import Image, ImageOps
from openai import OpenAI

from models import canonical

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "partite": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "giornata": {"type": ["integer", "null"]},
                    "data": {"type": ["string", "null"]},
                    "casa": {"type": "string"},
                    "gol_casa": {"type": "integer"},
                    "gol_ospite": {"type": "integer"},
                    "ospite": {"type": "string"},
                },
                "required": ["giornata", "data", "casa", "gol_casa", "gol_ospite", "ospite"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["partite"],
    "additionalProperties": False,
}

PROMPT = """Leggi lo screenshot di un campionato di calcio ed estrai ESCLUSIVAMENTE le partite terminate con un risultato numerico certo.
La squadra nella COLONNA A SINISTRA e' SEMPRE 'casa'; quella nella COLONNA A DESTRA e' SEMPRE 'ospite'.
Non invertire MAI le squadre, neppure se conosci il calendario del campionato.
In un punteggio '4 - 2', il 4 va in 'gol_casa' e il 2 in 'gol_ospite'.
Non inventare partite, nomi, punteggi, date o giornate. Ignora classifiche, intestazioni,
partite da disputare, rinvii, orari, pubblicita', rigori e risultati parziali.
Mantieni i nomi delle squadre cosi' come si leggono e la corretta associazione riga-per-riga.
Se la giornata o la data non sono leggibili nello screenshot, usa i valori predefiniti qui sotto.
Se neppure i valori predefiniti esistono, inserisci null per giornata/data.
Scrivi 'data' come GG/MM/AAAA. Nessun testo introduttivo.
"""


def _image_data_url(data: bytes) -> str:
    if len(data) > 15_000_000:
        raise ValueError("Immagine troppo grande: massimo 15 MB")
    with Image.open(io.BytesIO(data)) as image:
        img = ImageOps.exif_transpose(image).convert("RGB")
        # Limite adeguato per screenshot, evitando invii eccessivamente grandi.
        if max(img.size) > 2500:
            img.thumbnail((2500, 2500))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=91, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode("ascii")


def extract_matches(
    image_bytes: bytes, api_key: str, default_round: int | None,
    default_date: str, model: str = "gpt-4.1-mini",
) -> list[dict]:
    client = OpenAI(api_key=api_key, timeout=75, max_retries=1)
    instruction = (
        f"{PROMPT}\nGiornata predefinita: {default_round or 'non indicata'}. "
        f"Data predefinita: {default_date or 'non indicata'}."
    )
    response = client.responses.create(
        model=model,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": instruction},
                {"type": "input_image", "image_url": _image_data_url(image_bytes), "detail": "high"},
            ],
        }],
        text={"format": {"type": "json_schema", "name": "risultati_calcio", "strict": True, "schema": EXTRACTION_SCHEMA}},
    )
    if not response.output_text:
        raise RuntimeError("Il modello non ha restituito dati leggibili")
    result = json.loads(response.output_text)
    matches = []
    for item in result["partite"]:
        if item["giornata"] is None:
            item["giornata"] = default_round
        if not item["data"]:
            item["data"] = default_date
        matches.append(canonical(item))
    return matches
