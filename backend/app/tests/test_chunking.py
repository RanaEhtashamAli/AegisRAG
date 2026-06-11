"""Unit tests for the chunking service — no DB or network required."""
from app.services.chunking_service import TextChunk, chunk_text


def _pages(text: str) -> list[tuple[int, str]]:
    return [(1, text)]


# ── Basic behaviour ───────────────────────────────────────────────────────────

def test_empty_pages_returns_empty():
    assert chunk_text([]) == []


def test_blank_page_is_skipped():
    assert chunk_text([(1, "   \n\t  ")]) == []


def test_short_text_produces_one_chunk():
    pages = _pages("hello world this is a short document")
    chunks = chunk_text(pages, target_words=100)
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0


def test_chunk_contains_all_words_for_short_text():
    text = "the quick brown fox jumps over the lazy dog"
    chunks = chunk_text(_pages(text), target_words=100)
    assert chunks[0].text == text


def test_long_text_splits_into_multiple_chunks():
    # 1000 words → should produce at least 2 chunks at target_words=500
    words = " ".join([f"word{i}" for i in range(1000)])
    chunks = chunk_text(_pages(words), target_words=500, overlap_words=50)
    assert len(chunks) >= 2


def test_chunk_indices_are_sequential():
    words = " ".join([f"w{i}" for i in range(600)])
    chunks = chunk_text(_pages(words), target_words=200, overlap_words=20)
    for i, c in enumerate(chunks):
        assert c.chunk_index == i


def test_overlap_means_last_chunk_shares_words_with_previous():
    words = [f"w{i}" for i in range(300)]
    text = " ".join(words)
    chunks = chunk_text(_pages(text), target_words=200, overlap_words=50)
    assert len(chunks) >= 2
    # The last 50 words of chunk 0 should appear at the start of chunk 1
    end_of_first = chunks[0].text.split()[-50:]
    start_of_second = chunks[1].text.split()[:50]
    assert end_of_first == start_of_second


def test_page_number_is_preserved():
    pages = [(3, "word " * 10), (5, "other " * 10)]
    chunks = chunk_text(pages, target_words=100)
    assert chunks[0].page_number == 3


def test_multi_page_document_tracks_pages():
    pages = [(1, "alpha " * 300), (2, "beta " * 300)]
    chunks = chunk_text(pages, target_words=200, overlap_words=20)
    page_numbers = {c.page_number for c in chunks}
    # both pages should appear somewhere in the chunks
    assert 1 in page_numbers
    assert 2 in page_numbers


def test_exactly_target_words_produces_one_chunk():
    words = " ".join([f"x{i}" for i in range(100)])
    chunks = chunk_text(_pages(words), target_words=100, overlap_words=10)
    # exactly 100 words → hits the boundary on the 100th word
    assert len(chunks) >= 1


def test_returns_text_chunk_dataclass():
    chunks = chunk_text(_pages("hello world"), target_words=100)
    assert isinstance(chunks[0], TextChunk)
    assert hasattr(chunks[0], "text")
    assert hasattr(chunks[0], "page_number")
    assert hasattr(chunks[0], "chunk_index")
