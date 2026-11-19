"""Build submission-ready DOCX workbooks from the repository Markdown files.

Uses only the Python standard library and writes a minimal, valid WordprocessingML
package so the build remains reproducible in an offline submission environment.
"""

from __future__ import annotations

import argparse
import html
import re
import zipfile
from pathlib import Path


NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def esc(value: str) -> str:
    return html.escape(re.sub(r"\*\*|`|(?<!\w)\*(?=\S)|(?<=\S)\*(?!\w)", "", value), quote=False)


def run(text: str, *, bold: bool = False, italic: bool = False, size: int = 21) -> str:
    props = []
    if bold:
        props.append("<w:b/>")
    if italic:
        props.append("<w:i/>")
    props.extend([f'<w:sz w:val="{size}"/>', f'<w:szCs w:val="{size}"/>'])
    return f'<w:r><w:rPr>{"".join(props)}</w:rPr><w:t xml:space="preserve">{esc(text)}</w:t></w:r>'


def paragraph(text: str, style: str | None = None, *, bullet: bool = False) -> str:
    props = []
    if style:
        props.append(f'<w:pStyle w:val="{style}"/>')
    if bullet:
        props.append('<w:ind w:left="540" w:hanging="260"/>')
    prefix = run("• ", bold=True) if bullet else ""
    return f'<w:p><w:pPr>{"".join(props)}</w:pPr>{prefix}{run(text)}</w:p>'


def table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    cols = max(len(row) for row in rows)
    width = 9500 // cols
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for _ in range(cols))
    trs = []
    for ridx, row in enumerate(rows):
        cells = []
        for value in row + [""] * (cols - len(row)):
            shade = '<w:shd w:fill="E7E5EC"/>' if ridx == 0 else ""
            cell_run = run(value, bold=ridx == 0, size=17)
            cells.append(
                f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shade}'
                '<w:tcMar><w:top w:w="70" w:type="dxa"/><w:left w:w="90" w:type="dxa"/>'
                '<w:bottom w:w="70" w:type="dxa"/><w:right w:w="90" w:type="dxa"/></w:tcMar>'
                f'</w:tcPr><w:p>{cell_run}</w:p></w:tc>'
            )
        trs.append(f'<w:tr><w:trPr><w:cantSplit/></w:trPr>{"".join(cells)}</w:tr>')
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="9500" w:type="dxa"/>'
        '<w:tblBorders><w:top w:val="single" w:sz="4" w:color="999999"/>'
        '<w:left w:val="single" w:sz="4" w:color="999999"/>'
        '<w:bottom w:val="single" w:sz="4" w:color="999999"/>'
        '<w:right w:val="single" w:sz="4" w:color="999999"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="B7B7B7"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="B7B7B7"/></w:tblBorders></w:tblPr>'
        f'<w:tblGrid>{grid}</w:tblGrid>{"".join(trs)}</w:tbl>'
    )


def markdown_body(source: str) -> str:
    lines = source.splitlines()
    blocks: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            blocks.append(paragraph(heading.group(2), "Title" if level == 1 else f"Heading{min(level - 1, 3)}"))
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            rows = [[c.strip() for c in line.strip().strip("|").split("|")]]
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            blocks.append(table(rows))
            continue
        if line.startswith("```"):
            code: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            blocks.append(paragraph("\n".join(code), "Code"))
            continue
        if re.match(r"^\s*(?:[-*]|\d+\.)\s+", line):
            blocks.append(paragraph(re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", line), bullet=True))
            i += 1
            continue
        if line.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i].lstrip("> "))
                i += 1
            blocks.append(paragraph(" ".join(quote), "Quote"))
            continue
        parts = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,4}\s|\||>|```|\s*(?:[-*]|\d+\.)\s)", lines[i]):
            parts.append(lines[i].strip())
            i += 1
        blocks.append(paragraph(" ".join(parts)))
    return "".join(blocks)


def build(source: Path, output: Path) -> None:
    body = markdown_body(source.read_text(encoding="utf-8"))
    document = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{NS}"><w:body>{body}<w:sectPr>
<w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1020" w:bottom="1134" w:left="1020" w:header="567" w:footer="567"/>
</w:sectPr></w:body></w:document>'''
    styles = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{NS}">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Aptos" w:hAnsi="Aptos"/><w:sz w:val="21"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="110" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="240"/><w:keepNext/></w:pPr><w:rPr><w:b/><w:color w:val="474150"/><w:sz w:val="38"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="260" w:after="100"/><w:keepNext/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:color w:val="474150"/><w:sz w:val="29"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="200" w:after="80"/><w:keepNext/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:color w:val="6B6680"/><w:sz w:val="24"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/></w:pPr><w:rPr><w:b/><w:sz w:val="22"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="400"/><w:shd w:fill="F5FFF4"/></w:pPr><w:rPr><w:i/><w:color w:val="474150"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:basedOn w:val="Normal"/><w:pPr><w:shd w:fill="F2F2F2"/></w:pPr><w:rPr><w:rFonts w:ascii="Menlo" w:hAnsi="Menlo"/><w:sz w:val="17"/></w:rPr></w:style>
</w:styles>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>'''
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''
    doc_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", content_types)
        package.writestr("_rels/.rels", rels)
        package.writestr("word/document.xml", document)
        package.writestr("word/styles.xml", styles)
        package.writestr("word/_rels/document.xml.rels", doc_rels)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.source, args.output)
