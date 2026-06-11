"""Unit tests for document_parser — uses temporary files, no network."""
import textwrap

from app.services.document_parser import _group_into_pages, extract_pages

# ── _group_into_pages (pure function) ────────────────────────────────────────

def test_group_empty_returns_single_empty_page():
    pages = _group_into_pages([])
    assert pages == [(1, "")]


def test_group_short_paragraphs_into_one_page():
    paras = ["Hello world", "How are you"]
    pages = _group_into_pages(paras, words_per_page=400)
    assert len(pages) == 1
    assert "Hello world" in pages[0][1]


def test_group_many_words_splits_into_multiple_pages():
    # Each paragraph is 100 words; 5 paragraphs = 500 words; limit = 200 → 3 pages
    para = " ".join([f"word{i}" for i in range(100)])
    pages = _group_into_pages([para] * 5, words_per_page=200)
    assert len(pages) >= 2


def test_group_page_numbers_are_sequential():
    para = " ".join([f"word{i}" for i in range(100)])
    pages = _group_into_pages([para] * 10, words_per_page=200)
    for i, (num, _) in enumerate(pages, start=1):
        assert num == i


def test_group_content_preserved():
    paras = ["alpha beta gamma", "delta epsilon"]
    pages = _group_into_pages(paras, words_per_page=400)
    combined = " ".join(p[1] for p in pages)
    assert "alpha" in combined
    assert "epsilon" in combined


# ── TXT extraction ────────────────────────────────────────────────────────────

def test_extract_txt_returns_pages(tmp_path):
    f = tmp_path / "doc.txt"
    f.write_text("Hello world.\n\nThis is a second paragraph.", encoding="utf-8")
    pages = extract_pages(str(f))
    assert len(pages) >= 1
    combined = " ".join(t for _, t in pages)
    assert "Hello world" in combined
    assert "second paragraph" in combined


def test_extract_txt_single_paragraph(tmp_path):
    f = tmp_path / "doc.txt"
    f.write_text("Just one paragraph here.", encoding="utf-8")
    pages = extract_pages(str(f))
    assert len(pages) == 1
    assert pages[0][0] == 1


def test_extract_txt_empty_file(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    pages = extract_pages(str(f))
    assert pages == [(1, "")]


def test_extract_txt_unicode(tmp_path):
    f = tmp_path / "unicode.txt"
    f.write_text("Héllo wörld — café naïve", encoding="utf-8")
    pages = extract_pages(str(f))
    combined = " ".join(t for _, t in pages)
    assert "café" in combined


# ── Markdown extraction ───────────────────────────────────────────────────────

def test_extract_markdown_headings_and_body(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text(
        textwrap.dedent("""\
        # Title

        First paragraph content.

        ## Section

        Second paragraph content.
        """),
        encoding="utf-8",
    )
    pages = extract_pages(str(f))
    combined = " ".join(t for _, t in pages)
    assert "First paragraph" in combined
    assert "Second paragraph" in combined


def test_extract_markdown_code_fences(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("```python\nprint('hello')\n```", encoding="utf-8")
    pages = extract_pages(str(f))
    combined = " ".join(t for _, t in pages)
    assert "print" in combined


def test_extract_markdown_empty(tmp_path):
    f = tmp_path / "empty.md"
    f.write_text("", encoding="utf-8")
    pages = extract_pages(str(f))
    # empty markdown → one empty pseudo-page
    assert pages == [(1, "")]


# ── Unknown extension falls back to txt ──────────────────────────────────────

def test_extract_unknown_extension_falls_back(tmp_path):
    f = tmp_path / "doc.log"
    f.write_text("Some log content here.", encoding="utf-8")
    pages = extract_pages(str(f))
    combined = " ".join(t for _, t in pages)
    assert "Some log content" in combined


# ── Page number contract ──────────────────────────────────────────────────────

def test_all_page_numbers_are_positive_integers(tmp_path):
    content = "\n\n".join([f"paragraph {i} " + "word " * 50 for i in range(10)])
    f = tmp_path / "long.txt"
    f.write_text(content, encoding="utf-8")
    pages = extract_pages(str(f))
    for num, _ in pages:
        assert isinstance(num, int)
        assert num >= 1
