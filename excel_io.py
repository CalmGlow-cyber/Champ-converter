"""Import/export XLSX delle sei colonne, senza dipendenze Excel esterne.

L'app produce un normale file XLSX: date realmente ordinabili, punteggi numerici,
filtro e intestazione bloccata. Legge anche XLSX standard con shared strings.
"""
from __future__ import annotations

import io
import re
import zipfile
from datetime import date, datetime, timedelta
from xml.etree import ElementTree as ET

from models import HEADERS, canonical, parse_date, validate

S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
ET.register_namespace("", S)
ET.register_namespace("r", R)


def q(ns: str, name: str) -> str:
    return "{" + ns + "}" + name


def _xml(root) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _serial(value: str) -> int:
    dt = datetime.strptime(value, "%d/%m/%Y").date()
    return (dt - date(1899, 12, 30)).days


def _date_from_serial(value: str) -> str:
    try:
        number = float(value)
        return (date(1899, 12, 30) + timedelta(days=int(number))).strftime("%d/%m/%Y")
    except (ValueError, TypeError, OverflowError):
        return str(value)


def _workbook_xml() -> bytes:
    root = ET.Element(q(S, "workbook"))
    sheets = ET.SubElement(root, q(S, "sheets"))
    ET.SubElement(sheets, q(S, "sheet"), {"name": "Risultati", "sheetId": "1", q(R, "id"): "rId1"})
    return _xml(root)


def _relationships_xml() -> bytes:
    rels = ET.Element(q(P, "Relationships"))
    ET.SubElement(rels, q(P, "Relationship"), {
        "Id": "rId1", "Type": R + "/worksheet", "Target": "worksheets/sheet1.xml"
    })
    ET.SubElement(rels, q(P, "Relationship"), {
        "Id": "rId2", "Type": R + "/styles", "Target": "styles.xml"
    })
    return _xml(rels)


def _root_rel_xml() -> bytes:
    root = ET.Element(q(P, "Relationships"))
    ET.SubElement(root, q(P, "Relationship"), {
        "Id": "rId1", "Type": R + "/officeDocument", "Target": "xl/workbook.xml"
    })
    return _xml(root)


def _types_xml() -> bytes:
    root = ET.Element(q(CT, "Types"))
    ET.SubElement(root, q(CT, "Default"), {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"})
    ET.SubElement(root, q(CT, "Default"), {"Extension": "xml", "ContentType": "application/xml"})
    for part, content_type in (
        ("/xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"),
        ("/xl/worksheets/sheet1.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"),
        ("/xl/styles.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"),
    ):
        ET.SubElement(root, q(CT, "Override"), {"PartName": part, "ContentType": content_type})
    return _xml(root)


def _styles_xml() -> bytes:
    root = ET.Element(q(S, "styleSheet"))
    fmts = ET.SubElement(root, q(S, "numFmts"), {"count": "1"})
    ET.SubElement(fmts, q(S, "numFmt"), {"numFmtId": "164", "formatCode": "dd/mm/yyyy"})
    fonts = ET.SubElement(root, q(S, "fonts"), {"count": "2"})
    font = ET.SubElement(fonts, q(S, "font"))
    ET.SubElement(font, q(S, "sz"), {"val": "11"})
    ET.SubElement(font, q(S, "name"), {"val": "Aptos"})
    font = ET.SubElement(fonts, q(S, "font"))
    ET.SubElement(font, q(S, "b"))
    ET.SubElement(font, q(S, "sz"), {"val": "11"})
    ET.SubElement(font, q(S, "color"), {"rgb": "FFFFFFFF"})
    ET.SubElement(font, q(S, "name"), {"val": "Aptos"})
    fills = ET.SubElement(root, q(S, "fills"), {"count": "4"})
    ET.SubElement(ET.SubElement(fills, q(S, "fill")), q(S, "patternFill"), {"patternType": "none"})
    ET.SubElement(ET.SubElement(fills, q(S, "fill")), q(S, "patternFill"), {"patternType": "gray125"})
    pf = ET.SubElement(ET.SubElement(fills, q(S, "fill")), q(S, "patternFill"), {"patternType": "solid"})
    ET.SubElement(pf, q(S, "fgColor"), {"rgb": "FF165C4A"})
    ET.SubElement(pf, q(S, "bgColor"), {"indexed": "64"})
    pf = ET.SubElement(ET.SubElement(fills, q(S, "fill")), q(S, "patternFill"), {"patternType": "solid"})
    ET.SubElement(pf, q(S, "fgColor"), {"rgb": "FFF1F6F3"})
    ET.SubElement(pf, q(S, "bgColor"), {"indexed": "64"})
    borders = ET.SubElement(root, q(S, "borders"), {"count": "1"})
    border = ET.SubElement(borders, q(S, "border"))
    for side in ("left", "right", "top", "bottom", "diagonal"):
        ET.SubElement(border, q(S, side))
    ET.SubElement(root, q(S, "cellStyleXfs"), {"count": "1"}).append(ET.Element(q(S, "xf"), {"numFmtId": "0", "fontId": "0", "fillId": "0", "borderId": "0"}))
    xfs = ET.SubElement(root, q(S, "cellXfs"), {"count": "7"})
    # 0: default; 1: header; 2: date; 3: even text; 4: alternate text; 5: alternate date; 6: even numeric
    entries = [
        (0, 0, 0, "left"), (0, 1, 2, "center"), (164, 0, 0, "center"),
        (0, 0, 0, "left"), (0, 0, 3, "left"), (164, 0, 3, "center"), (0, 0, 0, "center"),
    ]
    for nfmt, font_id, fill_id, align in entries:
        xf = ET.SubElement(xfs, q(S, "xf"), {
            "numFmtId": str(nfmt), "fontId": str(font_id), "fillId": str(fill_id),
            "borderId": "0", "xfId": "0", "applyAlignment": "1",
            "applyNumberFormat": "1" if nfmt else "0",
        })
        ET.SubElement(xf, q(S, "alignment"), {"horizontal": align, "vertical": "center"})
    ET.SubElement(root, q(S, "cellStyles"), {"count": "1"}).append(ET.Element(q(S, "cellStyle"), {"name": "Normal", "xfId": "0", "builtinId": "0"}))
    return _xml(root)


def _write_cell(row, col: int, row_idx: int, value, style: int):
    cell = ET.SubElement(row, q(S, "c"), {"r": f"{chr(65 + col)}{row_idx}", "s": str(style)})
    if isinstance(value, int):
        ET.SubElement(cell, q(S, "v")).text = str(value)
    else:
        cell.set("t", "inlineStr")
        inline = ET.SubElement(cell, q(S, "is"))
        t = ET.SubElement(inline, q(S, "t"))
        if str(value).startswith(" ") or str(value).endswith(" "):
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t.text = str(value)


def _sheet_xml(matches: list[dict]) -> bytes:
    root = ET.Element(q(S, "worksheet"))
    views = ET.SubElement(root, q(S, "sheetViews"))
    view = ET.SubElement(views, q(S, "sheetView"), {"workbookViewId": "0"})
    ET.SubElement(view, q(S, "pane"), {"ySplit": "1", "topLeftCell": "A2", "activePane": "bottomLeft", "state": "frozen"})
    ET.SubElement(view, q(S, "selection"), {"pane": "bottomLeft", "activeCell": "A2", "sqref": "A2"})
    root.append(ET.Element(q(S, "sheetFormatPr"), {"defaultRowHeight": "18"}))
    widths = ET.SubElement(root, q(S, "cols"))
    for col, width in enumerate((12, 16, 38, 14, 14, 38), start=1):
        ET.SubElement(widths, q(S, "col"), {"min": str(col), "max": str(col), "width": str(width), "customWidth": "1"})
    data = ET.SubElement(root, q(S, "sheetData"))
    header = ET.SubElement(data, q(S, "row"), {"r": "1", "ht": "26", "customHeight": "1"})
    for col, title in enumerate(HEADERS):
        _write_cell(header, col, 1, title, 1)
    for idx, m in enumerate(matches, start=2):
        node = ET.SubElement(data, q(S, "row"), {"r": str(idx), "ht": "21", "customHeight": "1"})
        alternate = idx % 2 == 1
        for col, header_name in enumerate(HEADERS):
            val = m[header_name]
            if header_name == "Data":
                val = _serial(val)
                style = 5 if alternate else 2
            elif header_name in ("Giornata", "Gol casa", "Gol ospite"):
                style = 4 if alternate else 6
            else:
                style = 4 if alternate else 3
            _write_cell(node, col, idx, val, style)
    ET.SubElement(root, q(S, "autoFilter"), {"ref": f"A1:F{max(1, len(matches) + 1)}"})
    ET.SubElement(root, q(S, "pageMargins"), {"left": "0.25", "right": "0.25", "top": "0.5", "bottom": "0.5", "header": "0.2", "footer": "0.2"})
    return _xml(root)


def export_xlsx(rows: list[dict]) -> bytes:
    matches = [canonical(m) for m in rows]
    for idx, match in enumerate(matches, start=2):
        problems = validate(match)
        if problems:
            raise ValueError(f"Riga {idx}: {', '.join(problems)}")
    contents = {
        "[Content_Types].xml": _types_xml(),
        "_rels/.rels": _root_rel_xml(),
        "xl/workbook.xml": _workbook_xml(),
        "xl/_rels/workbook.xml.rels": _relationships_xml(),
        "xl/styles.xml": _styles_xml(),
        "xl/worksheets/sheet1.xml": _sheet_xml(matches),
    }
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=7) as z:
        for filename, content in contents.items():
            z.writestr(filename, content)
    return out.getvalue()


def _sheet_path(z: zipfile.ZipFile) -> str:
    # Anche se Excel inserisce più fogli, si seleziona il primo del workbook.
    workbook = ET.fromstring(z.read("xl/workbook.xml"))
    sheet = workbook.find(f"{q(S, 'sheets')}/{q(S, 'sheet')}")
    if sheet is None:
        raise ValueError("Nessun foglio nel file Excel")
    rid = sheet.get(q(R, "id"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    for rel in rels.findall(q(P, "Relationship")):
        if rel.get("Id") == rid:
            target = rel.get("Target", "")
            if target.startswith("/xl/"):
                return target.lstrip("/")
            if target.startswith("xl/"):
                return target
            return "xl/" + target.lstrip("/")
    raise ValueError("Foglio Excel non trovato")


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.iter(q(S, "t"))) for si in root.findall(q(S, "si"))]


def import_xlsx(payload: bytes) -> list[dict]:
    if len(payload) > 15_000_000:
        raise ValueError("File Excel troppo grande (massimo 15 MB)")
    try:
        z = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise ValueError("Il file non è un XLSX valido") from exc
    with z:
        if sum(i.file_size for i in z.infolist()) > 30_000_000:
            raise ValueError("Il contenuto Excel supera il limite consentito")
        strings = _shared_strings(z)
        sheet = ET.fromstring(z.read(_sheet_path(z)))
        data = sheet.find(q(S, "sheetData"))
        if data is None:
            raise ValueError("Nessun dato nel file Excel")
        rows = []
        for row in data.findall(q(S, "row")):
            cells = {}
            for cell in row.findall(q(S, "c")):
                pos = cell.get("r", "")
                found = re.match(r"([A-Z]+)\d+", pos)
                if not found:
                    continue
                column_letters = found.group(1)
                col = 0
                for char in column_letters:
                    col = col * 26 + (ord(char) - 64)
                col -= 1
                if col >= len(HEADERS):
                    continue
                kind = cell.get("t", "")
                raw = cell.findtext(q(S, "v"), default="")
                if kind == "inlineStr":
                    inline = cell.find(q(S, "is"))
                    value = "".join(t.text or "" for t in inline.iter(q(S, "t"))) if inline is not None else ""
                elif kind == "s":
                    value = strings[int(raw)] if raw else ""
                elif kind == "b":
                    value = "1" if raw == "1" else "0"
                else:
                    value = raw
                cells[col] = value
            rows.append([cells.get(i, "") for i in range(len(HEADERS))])
    if not rows or tuple(str(x).strip().casefold() for x in rows[0]) != tuple(h.casefold() for h in HEADERS):
        raise ValueError("Le prime sei colonne devono essere: " + " · ".join(HEADERS))
    matches = []
    for row in rows[1:]:
        if not any(str(x).strip() for x in row):
            continue
        record = dict(zip(HEADERS, row))
        if isinstance(record["Data"], str) and re.fullmatch(r"\d+(?:\.0+)?", record["Data"]):
            record["Data"] = _date_from_serial(record["Data"])
        record["Data"] = parse_date(record["Data"])
        matches.append(canonical(record))
    return matches
