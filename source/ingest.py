"""
Faz A: PDF -> chunk -> JSON.

Usage:
    python src/ingest.py data/raw/esp32_trm.pdf

Writes data/index/<doc_id>.json containing a list of Chunk dicts.
"""

import json
import re
import sys
from pathlib import Path

import fitz  # pymupdf

from models import Chunk

# Matches common datasheet/spec section headers, e.g.:
#   "6.3 GPIO Matrix"
#   "6.3.1 Register Description"
#   "Chapter 6: Peripherals"
#   "A.2 Electrical Characteristics"
SECTION_HEADER_PATTERNS = [
    re.compile(r"^(?P<num>\d+(\.\d+)*)\s+(?P<title>[A-Z][A-Za-z0-9 ,/\-()_]{3,80})$"),
    re.compile(r"^(?P<num>[A-Z](\.\d+)+)\s+(?P<title>[A-Z][A-Za-z0-9 ,/\-()_]{3,80})$"),
    re.compile(r"^Chapter\s+(?P<num>\d+)[:.]?\s*(?P<title>[A-Za-z0-9 ,/\-()_]{3,80})$"),
]

MIN_CHUNK_CHARS = 40  # skip near-empty trailing chunks


def is_section_header(line: str) -> tuple[bool, str]:
    """Return (True, normalized_title) if the line looks like a section header."""
    line = line.strip()
    if not line or len(line) > 100:
        return False, ""
    for pattern in SECTION_HEADER_PATTERNS:
        m = pattern.match(line)
        if m:
            num = m.group("num")
            title = m.group("title").strip()
            return True, f"{num} {title}"
    return False, ""


def extract_pages(pdf_path: Path) -> list[str]:
    """Return a list of page texts, one entry per page (1-indexed conceptually)."""
    doc = fitz.open(pdf_path)
    pages = [page.get_text("text") for page in doc]
    doc.close()
    return pages


def chunk_document(pages: list[str], doc_id: str, source_file: str) -> list[Chunk]:
    """
    Walk through page texts line by line. Whenever a line matches a section
    header pattern, start a new chunk. Track which pages each chunk spans.

    If no headers are found before the first one, that preamble becomes
    chunk 0 with a generic title so nothing is silently dropped.
    """
    chunks: list[Chunk] = []
    current_title = "Preamble"
    current_lines: list[str] = []
    current_page_start = 1
    chunk_index = 0

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

    for page_num, page_text in enumerate(pages, start=1):
        for line in page_text.splitlines():
            is_header, title = is_section_header(line)
            if is_header:
                # close out the previous chunk at the previous page
                flush(end_page=page_num)
                current_title = title
                current_lines = []
                current_page_start = page_num
            else:
                current_lines.append(line)

    # flush whatever is left at the end of the document
    flush(end_page=len(pages))
    return chunks


def ingest(pdf_path: Path, index_dir: Path) -> list[Chunk]:
    doc_id = pdf_path.stem
    pages = extract_pages(pdf_path)
    chunks = chunk_document(pages, doc_id=doc_id, source_file=pdf_path.name)

    index_dir.mkdir(parents=True, exist_ok=True)
    out_path = index_dir / f"{doc_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([c.to_dict() for c in chunks], f, ensure_ascii=False, indent=2)

    print(f"[ingest] {pdf_path.name}: {len(pages)} pages -> {len(chunks)} sections")
    print(f"[ingest] wrote {out_path}")
    return chunks


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python src/ingest.py <path-to-pdf>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1]).resolve()
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        sys.exit(1)

    project_root = Path(__file__).resolve().parent.parent
    index_dir = project_root / "data" / "index"
    ingest(pdf_path, index_dir)
