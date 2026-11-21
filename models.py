"""Validazione e aggiornamento dei risultati di campionato."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any

HEADERS = ("Giornata", "Data", "Casa", "Gol casa", "Gol ospite", "Ospite")


def parse_date(value: Any) -> str:
    """Restituisce una data in formato gg/mm/aaaa o una stringa vuota."""
    if value is None or str(value).strip().lower() in {"", "none", "null", "nan", "nat"}:
        return ""
    text = str(value).strip().split(" ")[0]
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%d/%m/%Y")
        except ValueError:
            pass
    return text


def _integer(value: Any) -> int | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        return None
    try:
        n = int(value)
        return n if float(value) == n else None
    except (TypeError, ValueError, OverflowError):
        return None


def canonical(row: dict[str, Any]) -> dict[str, Any]:
    """Uniforma una riga letta dall'API, dall'editor o da Excel."""
    # Le chiavi del formato API sono diverse da quelle visualizzate in tabella.
    aliases = {
        "Giornata": ("Giornata", "giornata"),
        "Data": ("Data", "data"),
        "Casa": ("Casa", "casa"),
        "Gol casa": ("Gol casa", "gol_casa"),
        "Gol ospite": ("Gol ospite", "gol_ospite"),
        "Ospite": ("Ospite", "ospite"),
    }
    vals = {}
    for dest, options in aliases.items():
        vals[dest] = next((row[k] for k in options if k in row), None)
    return {
        "Giornata": _integer(vals["Giornata"]),
        "Data": parse_date(vals["Data"]),
        "Casa": str(vals["Casa"] or "").strip(),
        "Gol casa": _integer(vals["Gol casa"]),
        "Gol ospite": _integer(vals["Gol ospite"]),
        "Ospite": str(vals["Ospite"] or "").strip(),
    }


def validate(row: dict[str, Any]) -> list[str]:
    m = canonical(row)
    problems = []
    if m["Giornata"] is None or m["Giornata"] < 1:
        problems.append("Giornata mancante o non valida")
    if not m["Data"]:
        problems.append("Data mancante")
    else:
        try:
            datetime.strptime(m["Data"], "%d/%m/%Y")
        except ValueError:
            problems.append("Data non valida (usare gg/mm/aaaa)")
    if not m["Casa"]:
        problems.append("Squadra di casa mancante")
    if not m["Ospite"]:
        problems.append("Squadra ospite mancante")
    for k in ("Gol casa", "Gol ospite"):
        if m[k] is None or not (0 <= m[k] <= 99):
            problems.append(f"{k} non valido")
    return problems


def _teamkey(team: str) -> str:
    text = unicodedata.normalize("NFKD", team).casefold()
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", text)


def _match_key(m: dict[str, Any]) -> tuple:
    # La partita di ritorno è distinta dalla giornata, anche con gli stessi avversari.
    return m["Giornata"], _teamkey(m["Casa"]), _teamkey(m["Ospite"])


def merge_rows(previous: list[dict], new: list[dict]) -> tuple[list[dict], int, int]:
    """Inserisce nuove partite e sostituisce quelle della stessa giornata e squadre."""
    combined: list[dict] = []
    indexes: dict[tuple, int] = {}
    added = updated = 0
    for source, rows in (("previous", previous), ("new", new)):
        for row in rows:
            m = canonical(row)
            key = _match_key(m)
            # Per righe incomplete si evita di consolidare chiavi vuote.
            if key[0] is None or not key[1] or not key[2]:
                combined.append(m)
            elif key in indexes:
                if source == "new" and combined[indexes[key]] != m:
                    combined[indexes[key]] = m
                    updated += 1
            else:
                indexes[key] = len(combined)
                combined.append(m)
                if source == "new":
                    added += 1
    return sort_rows(combined), added, updated


def sort_rows(rows: list[dict]) -> list[dict]:
    def key(row: dict):
        m = canonical(row)
        try:
            when = datetime.strptime(m["Data"], "%d/%m/%Y")
        except ValueError:
            when = datetime.max
        return (m["Giornata"] if m["Giornata"] is not None else 100000, when, _teamkey(m["Casa"]))
    return sorted((canonical(m) for m in rows), key=key)
