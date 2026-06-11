from dataclasses import dataclass


@dataclass
class TextChunk:
    text: str
    page_number: int | None
    chunk_index: int


def chunk_text(
    pages: list[tuple[int, str]],
    target_words: int = 900,
    overlap_words: int = 120,
) -> list[TextChunk]:
    """
    Split page text into overlapping word-based chunks.

    Each chunk targets `target_words` words. After emitting a chunk the next
    one starts `overlap_words` words before the end of the previous chunk to
    preserve context across chunk boundaries.
    """
    chunks: list[TextChunk] = []
    current_words: list[str] = []
    current_page: int | None = None
    chunk_index = 0

    for page_num, text in pages:
        if not text.strip():
            continue
        for word in text.split():
            current_words.append(word)
            if current_page is None:
                current_page = page_num
            if len(current_words) >= target_words:
                chunks.append(
                    TextChunk(
                        text=" ".join(current_words),
                        page_number=current_page,
                        chunk_index=chunk_index,
                    )
                )
                chunk_index += 1
                current_words = current_words[-overlap_words:]
                current_page = page_num  # overlap belongs to the current page

    if current_words:
        chunks.append(
            TextChunk(
                text=" ".join(current_words),
                page_number=current_page,
                chunk_index=chunk_index,
            )
        )

    return chunks
