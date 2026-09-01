# techdoc-search-mcp

An MCP server for task-scoped search over local technical PDFs — datasheets,
RFCs, application notes. Point it at a folder of PDFs and Claude can look up
a spec detail and get back the exact section, page, and source file, instead
of you scrolling through a 900-page manual.

## Scope (by design)

- **Local PDFs only.** No web search, no other formats (yet).
- **Lookup by default.** Tools return raw matching sections with citations;
  Claude does the interpreting. Optional `report` mode (summarized, multi-chunk
  synthesis via sampling or a free LLM API) and non-English tokenization are
  planned as opt-in modes, not defaults — see [Roadmap](#roadmap).

## Why not just paste the PDF into Claude?

For a single question on a single document, you probably could. This
matters at scale:

- **Cost/context**: uploading a 78-page datasheet directly costs ~150-250K
  tokens (text + page images) per message. A `search_techdoc` call returns
  only the top-5 relevant chunks — roughly 100x fewer tokens per question.
- **No re-upload**: the index persists on disk. Ask a question today, ask
  another next month, without re-attaching the file each time.
- **Scales to many documents**: indexing 10+ datasheets doesn't change how
  you query — `search_techdoc` searches across all of them at once.
- **Indexing and search cost nothing**: `ingest.py` and `search.py` run
  entirely locally (regex/font parsing + BM25), no LLM calls. Only the
  final interpretation step touches the model, on a small result set.

Measured on a real 78-page ESP32 datasheet (95 indexed sections,
120,969 characters): full-document cost per question ≈ $0.40 equivalent
(Sonnet 5 API pricing) vs. ≈ $0.004 via `search_techdoc` — about 100x.

## Status: MVP complete ✅

- [x] **Phase A** — PDF → section-aware chunks → JSON index (`source/ingest.py`)
- [x] **Phase B** — BM25 search over indexed chunks (`source/search.py`)
- [x] **Phase C** — MCP server wrapping 3 tools (`source/server.py`)
- [x] **Phase D** — End-to-end test via Claude Code, verified working
- [ ] **Phase E** — `report` mode / language options (future)
- [ ] **Phase F** — Polish + real-world datasheet examples

## How it works

```
PDF file
    -> ingest.py extracts text per page, detects section headers via regex,
       groups text into Chunks (models.py), writes data/index/<doc>.json
    -> search.py loads all indexed Chunks, builds a BM25 index, ranks
       sections against a query, returns SearchResult objects
    -> server.py exposes both as MCP tools Claude can call directly
```

## Setup

```bash
pip3 install pymupdf rank-bm25 mcp
```

## Usage

### 1. Index a PDF

```bash
cd source
python3 ingest.py /path/to/your_datasheet.pdf
```

Writes `data/index/<filename>.json` — a list of chunks with source file,
section title, page range, and text.

### 2. Search from the command line (no MCP needed)

```bash
python3 search.py "UART baud rate register" --top-k 5
```

### 3. Connect to Claude Code

```bash
claude mcp add techdoc-search -- python3 /absolute/path/to/techdoc-search-mcp/source/server.py
```

Then inside Claude Code:

```
/mcp
```

should show `techdoc-search · connected` with 3 tools available:

| Tool | What it does |
|---|---|
| `index_document(filepath)` | Indexes a new PDF |
| `search_techdoc(query, top_k=5)` | Returns the most relevant sections for a query, with source + page |
| `list_indexed_docs()` | Lists what's currently indexed |

### Example

Asking Claude Code:

> "techdoc-search server'ındaki search_techdoc tool'unu kullanarak UART baud rate register'ı bul"

returns the matching register description with its exact page and section,
which Claude then explains in context (e.g. computing a real `CLK_DIV` value
for a target baud rate) — the server only supplies the raw, cited match.

## Roadmap

- **Phase E**: optional `mode="report"` (multi-chunk synthesis, likely via
  MCP sampling so the server doesn't need its own API key) and `lang=`
  support for non-English documents — both opt-in per call, not defaults.
- **Phase F**: test against a real multi-hundred-page datasheet (ESP32 TRM,
  STM32 reference manual, etc.) instead of the synthetic sample used during
  development.

## Tech stack

Python 3.11+, [PyMuPDF](https://pymupdf.readthedocs.io/), `rank-bm25`,
official `mcp` Python SDK (v2, `MCPServer`), stdio transport.