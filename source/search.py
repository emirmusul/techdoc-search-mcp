"""
Faz B: BM25 tabanli arama motoru.

data/index/ altindaki tüm JSON dosyalarini yükler, rank-bm25 ile
tokenize ederek aranabilir hale getirir.

Usage:
    python source/search.py "GPIO interrupt configuration" --top-k 5
"""

import json
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from models import Chunk, SearchResult


def _tokenize(text: str) -> list[str]:
    """Lowercase + split on non-alphanumeric characters."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _load_chunks(index_dir: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for json_file in sorted(index_dir.glob("*.json")):
        with open(json_file, encoding="utf-8") as f:
            records = json.load(f)
        for record in records:
            chunks.append(Chunk.from_dict(record))
    return chunks


class SearchIndex:
    def __init__(self, index_dir: Path):
        self._chunks = _load_chunks(index_dir)
        if not self._chunks:
            raise ValueError(f"No chunks found in {index_dir}. Run ingest first.")
        tokenized = [_tokenize(c.text) for c in self._chunks]
        self._bm25 = BM25Okapi(tokenized)

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        query_tokens = _tokenize(query)
        scores = self._bm25.get_scores(query_tokens)
        # argsort descending, take top_k
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        results = []
        for i in ranked:
            chunk = self._chunks[i]
            results.append(
                SearchResult(
                    text=chunk.text,
                    source_file=chunk.source_file,
                    section=chunk.section_title,
                    page=chunk.page_start,
                    score=float(scores[i]),
                )
            )
        return results


def search(query: str, top_k: int = 5, index_dir: Path | None = None) -> list[SearchResult]:
    """Module-level convenience function. Loads the index on every call (stateless)."""
    if index_dir is None:
        index_dir = Path(__file__).resolve().parent.parent / "data" / "index"
    idx = SearchIndex(index_dir)
    return idx.search(query, top_k=top_k)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Search the techdoc index.")
    parser.add_argument("query", help="Search query string")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    results = search(args.query, top_k=args.top_k)
    for rank, r in enumerate(results, 1):
        print(f"[{rank}] score={r.score:.4f}  {r.source_file}  p.{r.page}  «{r.section}»")
        print(f"    {r.text[:200].replace(chr(10), ' ')}")
        print()
