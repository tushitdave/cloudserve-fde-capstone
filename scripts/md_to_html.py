"""Minimal Markdown → standalone HTML for the submission documents (no third-party deps).

Supports headings, paragraphs, pipe tables, bullet/numbered lists, block quotes,
fenced code, **bold**, *italic*, `code` and [links](url). Used to render the
workbooks (then `textutil -convert docx`) and the report (then Chrome --print-to-pdf).

    python scripts/md_to_html.py input.md output.html [--title "..."]
"""

import argparse
import html
import re
from pathlib import Path

CSS = """
@page { size: A4; margin: 20mm 18mm 20mm 18mm; }
body { font-family: Georgia, 'Times New Roman', serif; font-size: 11pt; line-height: 1.45; color: #1d1d1f; }
h1 { font-size: 20pt; margin: 0 0 10pt; } h2 { font-size: 15pt; margin: 18pt 0 6pt; border-bottom: 1px solid #bbb; padding-bottom: 2pt; }
h3 { font-size: 12.5pt; margin: 14pt 0 4pt; } h4 { font-size: 11pt; margin: 10pt 0 4pt; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 9pt; page-break-inside: auto; }
th, td { border: 1px solid #999; padding: 3pt 5pt; vertical-align: top; text-align: left; }
th { background: #eee; } tr { page-break-inside: avoid; }
code { font-family: Menlo, Consolas, monospace; font-size: 8.5pt; background: #f3f3f3; padding: 0 2pt; overflow-wrap: anywhere; }
a { overflow-wrap: anywhere; }
pre { background: #f3f3f3; padding: 6pt; font-size: 7.5pt; white-space: pre-wrap; overflow-wrap: anywhere; }
blockquote { margin: 6pt 0 6pt 12pt; padding-left: 8pt; border-left: 3px solid #aaa; color: #333; }
.caption { font-size: 9pt; font-style: italic; margin-top: -4pt; }
.pagebreak { page-break-after: always; }
"""


def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?!\w)", r"<em>\1</em>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def convert(md: str) -> str:
    lines = md.splitlines()
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == "<!-- pagebreak -->":
            out.append('<div class="pagebreak"></div>'); i += 1; continue
        if line.startswith("```"):
            block = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(html.escape(lines[i])); i += 1
            out.append("<pre>" + "\n".join(block) + "</pre>"); i += 1; continue
        heading = re.match(r"^(#{1,4})\s+(.*)", line)
        if heading:
            level = len(heading.group(1))
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>"); i += 1; continue
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            rows = []
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>" for row in rows) + "</tbody></table>")
            continue
        if re.match(r"^\s*[-*]\s+", line) or re.match(r"^\s*\d+\.\s+", line):
            ordered = bool(re.match(r"^\s*\d+\.\s+", line))
            tag = "ol" if ordered else "ul"
            items = []
            while i < len(lines) and (re.match(r"^\s*[-*]\s+", lines[i]) or re.match(r"^\s*\d+\.\s+", lines[i])):
                items.append(re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", lines[i])); i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(item)}</li>" for item in items) + f"</{tag}>"); continue
        if line.startswith(">"):
            block = []
            while i < len(lines) and lines[i].startswith(">"):
                block.append(lines[i].lstrip("> ")); i += 1
            out.append("<blockquote>" + inline(" ".join(block)) + "</blockquote>"); continue
        if not line.strip():
            i += 1; continue
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,4}\s|\||>|```|\s*[-*]\s|\s*\d+\.\s)", lines[i]):
            para.append(lines[i].strip()); i += 1
        text = " ".join(para)
        cls = ' class="caption"' if re.match(r"^\*?(Table|Figure) \d+", text) else ""
        out.append(f"<p{cls}>{inline(text)}</p>")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title", default=None)
    args = parser.parse_args()
    md = args.input.read_text()
    title = args.title or next((l.lstrip("# ") for l in md.splitlines() if l.startswith("# ")), args.input.stem)
    args.output.write_text(f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
                           f"<style>{CSS}</style></head><body>{convert(md)}</body></html>")


if __name__ == "__main__":
    main()
