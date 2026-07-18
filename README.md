# mcp-techdoc-search

An MCP server for task-scoped search over local technical PDFs — datasheets,
RFCs, application notes. Point it at a folder of PDFs and Claude can look up
a spec detail and get back the exact section, page, and source file, instead
of you scrolling through a 900-page manual.

## Scope (by design)

- **Local PDFs only.** No web search, no other formats (yet).
- **Lookup by default.** Tools return raw matching sections with citations;
  Claude does the interpreting. Optional `report` mode (summarized, multi-chunk
  synthesis) and non-English tokenization are planned as opt-in modes, not
  defaults — see [Roadmap](#roadmap).

## Status

🚧 Work in progress. Built incrementally.

- [x] **Phase A** — PDF → section-aware chunks → JSON index (`src/ingest.py`)
- [ ] **Phase B** — BM25 search over indexed chunks (`src/search.py`)
- [ ] **Phase C** — MCP server wrapping 3 tools (`src/server.py`)
- [ ] **Phase D** — End-to-end test against `claude mcp add`
- [ ] **Phase E** — `report` mode / language options
- [ ] **Phase F** — Polish + examples

## Phase A: Ingestion

Extracts text page-by-page with PyMuPDF, detects section headers with a
regex pattern (`6.3 GPIO Matrix`, `6.4.1 UART_CLKDIV_REG`, `Chapter 6: ...`),
and groups text between headers into chunks. Each chunk records its source
file, section title, and page range.

```bash
pip install -e .
python src/ingest.py data/raw/your_datasheet.pdf
```

Output: `data/index/<filename>.json`, a list of chunks like:

```json
{
  "doc_id": "esp32_trm",
  "source_file": "esp32_trm.pdf",
  "section_title": "6.4.1 UART_CLKDIV_REG",
  "page_start": 4,
  "page_end": 4,
  "text": "...",
  "chunk_index": 3
}
```

## Roadmap

- **Phase B–D**: core MVP — BM25 search, MCP tool layer, real-world test
  against an ESP32 Technical Reference Manual.
- **Phase E+**: optional `mode="report"` (server synthesizes across chunks,
  likely via a free API like NVIDIA NIM) and `lang=` support for non-English
  documents — both opt-in per call, not defaults, to keep the base tool
  predictable.

## Tech stack

Python 3.11+, [PyMuPDF](https://pymupdf.readthedocs.io/), `rank-bm25`,
official `mcp` Python SDK, stdio transport.
