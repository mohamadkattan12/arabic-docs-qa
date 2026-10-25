import re
from dataclasses import dataclass

import pymupdf

# multilingual-e5-large truncates at 512 tokens: 2,400 Arabic chars measured 712 tokens, so 1,500
# (~445) fits. Overlap only applies when a paragraph is hard-split.
MAX_CHARS = 1500
OVERLAP = 300
HEADING = re.compile(r"^#{1,3}\s+(.+?)\s*$", re.MULTILINE)
ARABIC = re.compile(r"[؀-ۿ]")


@dataclass(frozen=True)
class Chunk:
    location: str
    content: str


def detect_lang(text: str) -> str:
    letters = sum(c.isalpha() for c in text) or 1
    return "ar" if len(ARABIC.findall(text)) / letters > 0.3 else "en"


def split_text(text: str) -> list[str]:
    """Group paragraphs into pieces of at most ~MAX_CHARS."""
    parts: list[str] = []
    for p in (p.strip() for p in re.split(r"\n\s*\n", text)):
        if len(p) > MAX_CHARS:
            parts += [p[i : i + MAX_CHARS] for i in range(0, len(p), MAX_CHARS - OVERLAP)]
        elif p:
            parts.append(p)
    pieces: list[str] = []
    current = ""
    for p in parts:
        if current and len(current) + len(p) + 2 > MAX_CHARS:
            pieces.append(current)
            current = p
        else:
            current = f"{current}\n\n{p}" if current else p
    if current:
        pieces.append(current)
    return pieces


def chunk_markdown(text: str, title: str) -> list[Chunk]:
    """One or more chunks per heading section; the heading is the citation location."""
    matches = list(HEADING.finditer(text))
    sections = [(title, text[: matches[0].start() if matches else len(text)])]
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((m.group(1), text[m.end() : end]))
    return [
        Chunk(heading, f"{heading}\n\n{piece}")
        for heading, body in sections
        for piece in split_text(body)
    ]


def chunk_plain(text: str) -> list[Chunk]:
    return [Chunk(f"part {i}", piece) for i, piece in enumerate(split_text(text), start=1)]


def chunk_pdf(data: bytes) -> list[Chunk]:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return [
            Chunk(f"page {n}", piece)
            for n, page in enumerate(doc, start=1)
            for piece in split_text(page.get_text())
        ]
