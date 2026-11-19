from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp/pdfs/final-report/demo_evidence_appendix.pdf"
SIZE = (1240, 1754)
INK = "#1d1d1f"
MUTED = "#555555"
GREEN = "#2f7d5b"
YELLOW = "#d99400"
LINE = "#aaaaaa"
REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def font(size: int, bold: bool = False):
    return ImageFont.truetype(BOLD if bold else REGULAR, size)


def wrapped(draw, text, width, fnt):
    result, current = [], ""
    for word in text.split():
        candidate = word if not current else f"{current} {word}"
        if draw.textbbox((0, 0), candidate, font=fnt)[2] <= width:
            current = candidate
        else:
            result.append(current)
            current = word
    if current:
        result.append(current)
    return result


def bullet(draw, y, text, color):
    draw.ellipse((95, y + 10, 109, y + 24), fill=color)
    fnt = font(23)
    for line in wrapped(draw, text, 1015, fnt):
        draw.text((128, y), line, font=fnt, fill=INK)
        y += 34
    return y + 13


page = Image.new("RGB", SIZE, "white")
draw = ImageDraw.Draw(page)
draw.text((85, 90), "Appendix F - Demo evidence and readiness", font=font(43, True), fill=INK)
draw.line((85, 150, 1155, 150), fill=LINE, width=2)

y = 190
intro = (
    "A visible-browser rehearsal on 17 November 2026 exercised the documented-answer and "
    "prompt-injection paths. The final implementation was then rebuilt from pinned dependencies "
    "inside Python 3.12 and Node 22 containers on 18 November 2026."
)
for line in wrapped(draw, intro, 1070, font(24)):
    draw.text((85, y), line, font=font(24), fill=INK)
    y += 37

y += 35
draw.text((85, y), "Verified evidence", font=font(31, True), fill=INK)
y += 55
for item in [
    "The browser released a pagination answer with exact DOC-API-002 passage citations.",
    "Instruction-integrity text was blocked before release and routed to a human handoff.",
    "The Knowledge Base displayed 29 approved articles, 145 passages, version lineage and exact offsets.",
    "Bounded document GraphRAG displayed 29 nodes and 44 curated policy-scoped edges.",
    "The Trust Center displayed Chroma status, four retrieval strategies, trace timing, outbox, cost, offline evaluation and drift.",
    "The full test suite passed 92 tests and the React production build completed successfully.",
    "Fresh container images built successfully; Nginx reached the API health endpoint and Chroma reported ready with 145 passages at 384 dimensions.",
]:
    y = bullet(draw, y, item, GREEN)

y += 25
draw.text((85, y), "Submission boundaries", font=font(31, True), fill=INK)
y += 55
for item in [
    "Human gold remains pending by design: candidate labels are not presented as adjudicated truth.",
    "The active embedding runtime is MiniLM/384; Azure ada-002 remains an optional legacy path.",
    "Provider token cost is zero in extractive/local runs and Azure pricing is not configured.",
    "The graph is curated document traversal, not an auto-generated entity ontology.",
]:
    y = bullet(draw, y, item, YELLOW)

draw.line((85, 1665, 1155, 1665), fill=LINE, width=2)
draw.text((85, 1680), "CloudServe Support Intelligence - Capstone Report", font=font(16), fill=MUTED)
draw.text((1125, 1680), "20", font=font(16), fill=MUTED)
OUT.parent.mkdir(parents=True, exist_ok=True)
page.save(OUT, "PDF", resolution=150.0)
print(OUT)
