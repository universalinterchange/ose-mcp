from typing import Any
from ose_mcp.storage.db import connect_refs as connect

def register_refs(mcp):
  @mcp.tool()
  def refs_init() -> dict[str, Any]:
    """Create refs tables + FTS index."""
    with connect() as con:
      con.executescript("""
      CREATE TABLE IF NOT EXISTS refs_pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE,
        title TEXT,
        text TEXT
      );

      CREATE VIRTUAL TABLE IF NOT EXISTS refs_fts
      USING fts5(title, text, content='refs_pages', content_rowid='id');
      """)
    return {"ok": True}

  @mcp.tool()
  def search_refs(query: str, limit: int = 5) -> dict[str, Any]:
    """Search cached references. Returns ids + snippets + URL."""
    with connect() as con:
      rows = con.execute(
        """
        SELECT p.id, p.title, p.url,
             snippet(refs_fts, 1, '[', ']', '…', 18) AS snippet
        FROM refs_fts
        JOIN refs_pages p ON p.id = refs_fts.rowid
        WHERE refs_fts MATCH ?
        LIMIT ?
        """,
        (query, int(limit)),
      ).fetchall()
    return {"results": [dict(r) for r in rows]}

  @mcp.tool()
  def open_ref(ref_id: int) -> dict[str, Any]:
    """Open a cached reference by id. Use URL as the citation."""
    with connect() as con:
      row = con.execute("SELECT id, title, url, text FROM refs_pages WHERE id=?", (int(ref_id),)).fetchone()
      if not row:
        raise ValueError("ref_id not found")
    return dict(row)

