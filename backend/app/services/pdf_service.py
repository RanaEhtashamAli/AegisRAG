from pypdf import PdfReader


def extract_pages(file_path: str) -> list[tuple[int, str]]:
    """Return list of (page_number, text) tuples, 1-indexed."""
    reader = PdfReader(file_path)
    pages: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append((i, text))
    return pages
