from __future__ import annotations

import base64
from collections import Counter
from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from app.models import Declaration, Photo


IMAGE_CX = 1_550_000
IMAGE_CY = 1_050_000


def _xml(value: object) -> str:
    return escape("" if value is None else str(value), {'"': "&quot;"})


def _cell_ref(row: int, col: int) -> str:
    name = ""
    while col:
        col, rem = divmod(col - 1, 26)
        name = chr(65 + rem) + name
    return f"{name}{row}"


def _inline_cell(row: int, col: int, value: object) -> str:
    return f'<c r="{_cell_ref(row, col)}" t="inlineStr"><is><t>{_xml(value)}</t></is></c>'


def _number_cell(row: int, col: int, value: int | float) -> str:
    return f'<c r="{_cell_ref(row, col)}"><v>{value}</v></c>'


def _row(row_idx: int, values: list[object], height: int | None = None) -> str:
    height_attr = f' ht="{height}" customHeight="1"' if height else ""
    cells = []
    for col_idx, value in enumerate(values, 1):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            cells.append(_number_cell(row_idx, col_idx, value))
        else:
            cells.append(_inline_cell(row_idx, col_idx, value))
    return f'<row r="{row_idx}"{height_attr}>{"".join(cells)}</row>'


def _sheet_xml(rows: list[str], max_row: int, max_col: int, drawing: bool = False) -> str:
    drawing_xml = '<drawing r:id="rId1"/>' if drawing else ""
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <dimension ref="A1:{_cell_ref(max_row, max_col)}"/>
  <sheetViews><sheetView workbookViewId="0"/></sheetViews>
  <sheetFormatPr defaultRowHeight="18"/>
  <cols>
    <col min="1" max="1" width="18" customWidth="1"/>
    <col min="2" max="2" width="42" customWidth="1"/>
    <col min="3" max="3" width="24" customWidth="1"/>
    <col min="4" max="8" width="18" customWidth="1"/>
    <col min="9" max="9" width="20" customWidth="1"/>
    <col min="10" max="11" width="26" customWidth="1"/>
  </cols>
  <sheetData>{"".join(rows)}</sheetData>
  {drawing_xml}
</worksheet>'''


def _photo_bytes(photo: Photo) -> tuple[bytes, str] | None:
    content_type = (photo.content_type or "").lower()
    raw: bytes | None = None
    if photo.data_url and "," in photo.data_url:
        header, payload = photo.data_url.split(",", 1)
        raw = base64.b64decode(payload)
        if "image/png" in header:
            content_type = "image/png"
        elif "image/jpeg" in header or "image/jpg" in header:
            content_type = "image/jpeg"
    elif photo.path:
        path = Path(photo.path)
        if path.exists():
            raw = path.read_bytes()
    if not raw:
        return None
    if "png" in content_type:
        return raw, "png"
    return raw, "jpeg"


def _content_types(image_extensions: list[str]) -> str:
    defaults = {
        "rels": "application/vnd.openxmlformats-package.relationships+xml",
        "xml": "application/xml",
    }
    if "png" in image_extensions:
        defaults["png"] = "image/png"
    if "jpeg" in image_extensions:
        defaults["jpeg"] = "image/jpeg"
    default_xml = "".join(f'<Default Extension="{ext}" ContentType="{ctype}"/>' for ext, ctype in defaults.items())
    override_parts = [
        ("/docProps/app.xml", "application/vnd.openxmlformats-officedocument.extended-properties+xml"),
        ("/docProps/core.xml", "application/vnd.openxmlformats-package.core-properties+xml"),
        ("/xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"),
        ("/xl/styles.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"),
        ("/xl/worksheets/sheet1.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"),
        ("/xl/worksheets/sheet2.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"),
    ]
    if image_extensions:
        override_parts.append(("/xl/drawings/drawing1.xml", "application/vnd.openxmlformats-officedocument.drawing+xml"))
    overrides = "".join(f'<Override PartName="{part}" ContentType="{ctype}"/>' for part, ctype in override_parts)
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">{default_xml}{overrides}</Types>'''


def _drawing_xml(images: list[dict[str, object]]) -> str:
    anchors = []
    for idx, item in enumerate(images, 1):
        row = int(item["row"]) - 1
        col = int(item["col"]) - 1
        anchors.append(f'''
  <xdr:oneCellAnchor>
    <xdr:from><xdr:col>{col}</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>{row}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>
    <xdr:ext cx="{IMAGE_CX}" cy="{IMAGE_CY}"/>
    <xdr:pic>
      <xdr:nvPicPr><xdr:cNvPr id="{idx}" name="Image {idx}"/><xdr:cNvPicPr/></xdr:nvPicPr>
      <xdr:blipFill><a:blip r:embed="rId{idx}"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill>
      <xdr:spPr><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr>
    </xdr:pic>
    <xdr:clientData/>
  </xdr:oneCellAnchor>''')
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
{"".join(anchors)}
</xdr:wsDr>'''


def _drawing_rels(images: list[dict[str, object]]) -> str:
    rels = "".join(
        f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image{idx}.{item["ext"]}"/>'
        for idx, item in enumerate(images, 1)
    )
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>'''


def _status_label(value: object) -> str:
    labels = {
        "nouvelle": "Nouvelle",
        "analyse": "En analyse",
        "affecte": "Affecté",
        "planifie": "Planifié",
        "realisee": "Réalisée",
        "cloture": "Clôturé",
    }
    raw = getattr(value, "value", value)
    return labels.get(str(raw), str(raw or ""))


def _value(value: object) -> str:
    raw = getattr(value, "value", value)
    return "" if raw is None else str(raw)


def build_declarations_xlsx(declarations: list[Declaration]) -> bytes:
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    totals = Counter(_value(declaration.status) for declaration in declarations)
    ateliers = Counter(declaration.atelier for declaration in declarations)
    summary_values: list[list[object]] = [
        ["Archive Gestion Précurseurs", ""],
        ["Date export", now],
        ["Total déclarations", len(declarations)],
        ["Déclarations ouvertes", len([d for d in declarations if _value(d.status) != "cloture"])],
        ["Déclarations clôturées", totals.get("cloture", 0)],
    ]
    summary_values.extend([f"Atelier - {atelier}", count] for atelier, count in sorted(ateliers.items()))
    summary_rows = [_row(idx, row) for idx, row in enumerate(summary_values, 1)]

    headers = [
        "Numéro précurseur",
        "Nom précurseur",
        "Atelier ciblé",
        "Catégorie",
        "Gravité",
        "Statut",
        "Date création",
        "Date limite traitement",
        "Date clôture",
        "Images jointes à la déclaration",
        "Images après intervention",
    ]
    declaration_rows = [_row(1, headers, height=24)]
    images: list[dict[str, object]] = []
    image_payloads: list[tuple[bytes, str]] = []
    current_row = 2
    for declaration in declarations:
        declaration_photos = [p for p in declaration.photos if (p.phase or "declaration") != "intervention"]
        intervention_photos = [p for p in declaration.photos if (p.phase or "declaration") == "intervention"]
        row_count = max(1, len(declaration_photos), len(intervention_photos))
        for idx in range(row_count):
            values = [
                declaration.reference,
                declaration.description,
                declaration.atelier,
                _value(declaration.category),
                _value(declaration.real_gravity),
                _status_label(declaration.status),
                declaration.created_at.strftime("%d/%m/%Y %H:%M") if declaration.created_at else "",
                declaration.sla_date or "",
                declaration.closed_at.strftime("%d/%m/%Y %H:%M") if declaration.closed_at else "",
                f"Image {idx + 1}" if idx < len(declaration_photos) else "",
                f"Image {idx + 1}" if idx < len(intervention_photos) else "",
            ]
            declaration_rows.append(_row(current_row, values, height=92 if (idx < len(declaration_photos) or idx < len(intervention_photos)) else None))
            for col, photos in ((10, declaration_photos), (11, intervention_photos)):
                if idx >= len(photos):
                    continue
                photo_payload = _photo_bytes(photos[idx])
                if not photo_payload:
                    continue
                image_payloads.append(photo_payload)
                images.append({"row": current_row, "col": col, "ext": photo_payload[1]})
            current_row += 1

    output = BytesIO()
    image_extensions = [ext for _, ext in image_payloads]
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types(image_extensions))
        archive.writestr("_rels/.rels", '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>''')
        archive.writestr("docProps/app.xml", '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Gesprec</Application></Properties>''')
        archive.writestr("docProps/core.xml", f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>Archive Gestion Précurseurs</dc:title><dc:creator>Gesprec</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">{datetime.utcnow().isoformat()}Z</dcterms:created></cp:coreProperties>''')
        archive.writestr("xl/workbook.xml", '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Tableau de bord" sheetId="1" r:id="rId1"/>
    <sheet name="Declarations" sheetId="2" r:id="rId2"/>
  </sheets>
</workbook>''')
        archive.writestr("xl/_rels/workbook.xml.rels", '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>''')
        archive.writestr("xl/styles.xml", '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts><fills count="1"><fill><patternFill patternType="none"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="1"><xf/></cellXfs></styleSheet>''')
        archive.writestr("xl/worksheets/sheet1.xml", _sheet_xml(summary_rows, max(len(summary_rows), 1), 2))
        archive.writestr("xl/worksheets/sheet2.xml", _sheet_xml(declaration_rows, max(current_row - 1, 1), 11, drawing=bool(images)))
        if images:
            archive.writestr("xl/worksheets/_rels/sheet2.xml.rels", '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing1.xml"/></Relationships>''')
            archive.writestr("xl/drawings/drawing1.xml", _drawing_xml(images))
            archive.writestr("xl/drawings/_rels/drawing1.xml.rels", _drawing_rels(images))
            for idx, (payload, ext) in enumerate(image_payloads, 1):
                archive.writestr(f"xl/media/image{idx}.{ext}", payload)
    return output.getvalue()
