"""
Faz A: PDF -> chunk -> JSON.

Usage:
    python source/ingest.py data/raw/esp32_trm.pdf

Writes data/index/<doc_id>.json containing a list of Chunk dicts.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import fitz  # pymupdf

from models import Chunk

MIN_CHUNK_CHARS = 40  # skip near-empty trailing chunks

# A line is a header candidate if its font size exceeds the document's most
# common (body) font size by this factor. Found empirically: body text sits
# at one dominant size (e.g. 10pt) and real headers are noticeably larger
# (12-14pt+). Regex-on-text was tried first but produced both false
# negatives (real datasheets often split "6.3" and "GPIO Matrix" across two
# lines) and false positives (ordinary text like "2.4 GHz Transmitter" looks
# like a numbered section to a regex, but is unrelated to layout).
HEADER_SIZE_FACTOR = 1.15
MAX_HEADER_LINE_CHARS = 100


def extract_lines_with_fonts(pdf_path: Path) -> list[list[tuple[str, float]]]:
    """
    Return per-page lists of (line_text, max_font_size_in_line).

    Uses PyMuPDF's "dict" extraction mode instead of plain "text" mode so we
    can see each line's font size -- this is what makes header detection
    possible without guessing at text patterns.
    """
    doc = fitz.open(pdf_path)
    pages: list[list[tuple[str, float]]] = []
    for page in doc:
        raw = page.get_text("dict")
        lines: list[tuple[str, float]] = []
        for block in raw.get("blocks", []):
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans).strip()
                if not text:
                    continue
                max_size = max(s["size"] for s in spans)
                lines.append((text, max_size))
        pages.append(lines)
    doc.close()
    return pages


def determine_body_size(pages: list[list[tuple[str, float]]]) -> float:
    """The most frequently occurring font size across the document -- our proxy for 'body text'."""
    sizes = Counter(round(size, 1) for page in pages for _, size in page)
    if not sizes:
        return 10.0
    return sizes.most_common(1)[0][0]


def is_header_line(text: str, size: float, body_size: float) -> bool:
    """A line counts as a header candidate if it's short and noticeably larger than body text."""
    if not text or len(text) > MAX_HEADER_LINE_CHARS:
        return False
    return size > body_size * HEADER_SIZE_FACTOR


def chunk_document(
    pages: list[list[tuple[str, float]]], doc_id: str, source_file: str, body_size: float
) -> list[Chunk]:
    """
    Walk through page lines. Whenever a line is header-sized, it joins a
    "pending header group" -- this is what lets us merge a real-world
    two-line header like "6.3" + "GPIO Matrix" (each its own line, both
    larger than body text) into a single title "6.3 GPIO Matrix". The
    group closes the moment a normal-sized (body) line appears.

    If no headers are found before the first one, that preamble becomes
    chunk 0 with a generic title so nothing is silently dropped.
    """
    chunks: list[Chunk] = []
    current_title = "Preamble"
    current_lines: list[str] = []
    current_page_start = 1
    chunk_index = 0

    pending_header_parts: list[str] = []
    pending_header_page: int | None = None

    def flush(end_page: int):
        nonlocal chunk_index
        text = "\n".join(current_lines).strip()
        if len(text) >= MIN_CHUNK_CHARS:
            chunks.append(
                Chunk(
                    doc_id=doc_id,
                    source_file=source_file,
                    section_title=current_title,
                    page_start=current_page_start,
                    page_end=end_page,
                    text=text,
                    chunk_index=chunk_index,
                )
            )
            chunk_index += 1

    def close_pending_header():
        """A header group ended (a body line showed up) -- commit it as the new title."""
        nonlocal current_title, current_page_start, pending_header_parts, pending_header_page
        if pending_header_parts:
            current_title = " ".join(pending_header_parts)
            current_page_start = pending_header_page
            pending_header_parts = []
            pending_header_page = None

    for page_num, lines in enumerate(pages, start=1):
        for text, size in lines:
            if is_header_line(text, size, body_size):
                if not pending_header_parts:
                    # first header-sized line of a new group -> the previous
                    # section's body is now complete, commit it
                    flush(end_page=page_num)
                    current_lines = []
                pending_header_parts.append(text)
                if pending_header_page is None:
                    pending_header_page = page_num
            else:
                close_pending_header()
                current_lines.append(text)

    close_pending_header()
    flush(end_page=len(pages))
    return chunks


def ingest(pdf_path: Path, index_dir: Path) -> list[Chunk]:
    doc_id = pdf_path.stem
    pages = extract_lines_with_fonts(pdf_path)
    body_size = determine_body_size(pages)
    chunks = chunk_document(pages, doc_id=doc_id, source_file=pdf_path.name, body_size=body_size)

    index_dir.mkdir(parents=True, exist_ok=True)
    out_path = index_dir / f"{doc_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([c.to_dict() for c in chunks], f, ensure_ascii=False, indent=2)

    print(f"[ingest] {pdf_path.name}: {len(pages)} pages -> {len(chunks)} sections")
    print(f"[ingest] wrote {out_path}")
    return chunks


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python source/ingest.py <path-to-pdf>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1]).resolve()
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        sys.exit(1)

    project_root = Path(__file__).resolve().parent.parent
    index_dir = project_root / "data" / "index"
    ingest(pdf_path, index_dir)