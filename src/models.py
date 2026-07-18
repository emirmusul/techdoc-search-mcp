"""Shared data structures for mcp-techdoc-search."""

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Chunk:
    """A single indexed section of a document."""

    doc_id: str          # e.g. "esp32_trm" (filename without extension)
    source_file: str     # e.g. "esp32_trm.pdf"
    section_title: str   # e.g. "6.3 GPIO Matrix"
    page_start: int       # 1-indexed page where the section begins
    page_end: int         # 1-indexed page where the section ends
    text: str             # the extracted section text
    chunk_index: int      # order within the document

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Chunk":
        return Chunk(**d)


@dataclass
class SearchResult:
    """A single scored search hit, ready to return through the MCP tool."""

    text: str
    source_file: str
    section: str
    page: int
    score: float

    def to_dict(self) -> dict:
        return asdict(self)
