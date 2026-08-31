"""
Faz C: MCP server katmani.

ingest.py ve search.py'daki fonksiyonlari MCP tool'lari olarak disariya acar.
Yeni arama/indeksleme mantigi eklemez -- sadece var olan islevi Claude'un
cagirabilecegi hale getirir.

Claude Desktop'a baglamak icin claude_desktop_config.json'a:

    {
      "mcpServers": {
        "techdoc-search": {
          "command": "python3",
          "args": ["/tam/yol/source/server.py"]
        }
      }
    }
"""

import json
import sys
from pathlib import Path

# server.py'nin kendi klasorunu sys.path'e ekliyoruz ki "from models import ..."
# gibi duz importlar, script'in nereden calistirildigina bakmaksizin calissin.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server import MCPServer

from ingest import ingest as run_ingest
from search import search as run_search

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = PROJECT_ROOT / "data" / "index"

mcp = MCPServer("techdoc-search")


@mcp.tool()
def index_document(filepath: str) -> dict:
    """
    Bir PDF datasheet/spec dosyasini indeksler.

    filepath: PDF'in tam ya da goreli dosya yolu.
    Basariliysa kac bolum bulundugunu doner.
    """
    pdf_path = Path(filepath).resolve()
    if not pdf_path.exists():
        return {"status": "error", "message": f"File not found: {pdf_path}"}
    if pdf_path.suffix.lower() != ".pdf":
        return {"status": "error", "message": f"Not a PDF file: {pdf_path}"}

    chunks = run_ingest(pdf_path, INDEX_DIR)
    return {
        "status": "indexed",
        "filepath": str(pdf_path),
        "sections_found": len(chunks),
    }


@mcp.tool()
def search_techdoc(query: str, top_k: int = 5) -> list[dict]:
    """
    Indekslenmis dokumanlarda sorguya en alakali bolumleri arar.

    query: dogal dil sorgusu, orn. "UART baud rate register".
    top_k: kac sonuc donecegi (varsayilan 5).
    Her sonuc; metin, kaynak dosya, bolum basligi, sayfa ve skor icerir.
    """
    if not INDEX_DIR.exists() or not any(INDEX_DIR.glob("*.json")):
        return []

    results = run_search(query, top_k=top_k, index_dir=INDEX_DIR)
    return [r.to_dict() for r in results]


@mcp.tool()
def list_indexed_docs() -> list[dict]:
    """Su ana kadar indekslenmis dokumanlari ve bolum sayilarini listeler."""
    if not INDEX_DIR.exists():
        return []

    docs = []
    for json_file in sorted(INDEX_DIR.glob("*.json")):
        with open(json_file, encoding="utf-8") as f:
            records = json.load(f)
        source_file = records[0]["source_file"] if records else json_file.stem
        docs.append(
            {
                "doc_id": json_file.stem,
                "source_file": source_file,
                "sections": len(records),
            }
        )
    return docs


if __name__ == "__main__":
    mcp.run()