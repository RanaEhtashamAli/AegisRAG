"""Multi-format document parser.

Returns a list of (page_number, text) tuples — the same contract as the
old pdf_service so tasks.py needs only a one-line swap.
"""
from __future__ import annotations

import os


def extract_pages(file_path: str) -> list[tuple[int, str]]:
    """Extract (page_number, text) tuples from PDF, DOCX, MD, or TXT."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return _extract_pdf(file_path)
    elif ext == ".docx":
        return _extract_docx(file_path)
    elif ext in (".md", ".markdown"):
        return _extract_markdown(file_path)
    elif ext == ".txt":
        return _extract_txt(file_path)
    else:
        # Attempt plain-text fallback for unknown extensions
        return _extract_txt(file_path)


def _extract_pdf(file_path: str) -> list[tuple[int, str]]:
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    pages: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append((i, text))
    return pages


def _extract_docx(file_path: str) -> list[tuple[int, str]]:
    from docx import Document

    doc = Document(file_path)
    # DOCX has no native page concept — group paragraphs into ~500-word pseudo-pages
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return _group_into_pages(paragraphs)


def _extract_markdown(file_path: str) -> list[tuple[int, str]]:
    from markdown_it import MarkdownIt

    with open(file_path, encoding="utf-8") as f:
        raw = f.read()

    md = MarkdownIt()
    tokens = md.parse(raw)
    # Collect inline text from all tokens
    lines: list[str] = []
    for tok in tokens:
        if tok.type == "inline" and tok.content:
            lines.append(tok.content.strip())
        elif tok.type == "fence" and tok.content:
            lines.append(tok.content.strip())

    return _group_into_pages(lines)


def _extract_txt(file_path: str) -> list[tuple[int, str]]:
    with open(file_path, encoding="utf-8", errors="replace") as f:
        text = f.read()

    # Split on double-newlines as paragraph boundaries
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return _group_into_pages(paragraphs)


def _group_into_pages(
    paragraphs: list[str], words_per_page: int = 400
) -> list[tuple[int, str]]:
    """Group text paragraphs into pseudo-pages by approximate word count."""
    if not paragraphs:
        return [(1, "")]

    pages: list[tuple[int, str]] = []
    current: list[str] = []
    current_words = 0
    page_num = 1

    for para in paragraphs:
        words = len(para.split())
        if current_words + words > words_per_page and current:
            pages.append((page_num, "\n\n".join(current)))
            page_num += 1
            current = []
            current_words = 0
        current.append(para)
        current_words += words

    if current:
        pages.append((page_num, "\n\n".join(current)))

    return pages
