import os
from ose_mcp.storage.db import connect_refs as connect

def build(pages: list[tuple[str, str, str]]):
    with connect() as con:
        con.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;

        CREATE TABLE IF NOT EXISTS refs_pages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          url TEXT UNIQUE,
          title TEXT,
          text TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS refs_fts
        USING fts5(title, text, content='refs_pages', content_rowid='id');
        """)

        for url, title, text in pages:
            con.execute(
                "INSERT INTO refs_pages(url,title,text) VALUES (?,?,?) "
                "ON CONFLICT(url) DO UPDATE SET title=excluded.title, text=excluded.text",
                (url, title, text),
            )

        # Rebuild FTS from content table
        con.execute("INSERT INTO refs_fts(refs_fts) VALUES('rebuild');")

if __name__ == "__main__":
    # Import crawl lazily so running build_index doesn't require requests/bs4 if you don't want it
    from ingest.ose_srd_crawl import crawl

    max_pages = int(os.environ.get("OSE_MCP_MAXPAGES", "300"))
    delay_s = float(os.environ.get("OSE_MCP_DELAY", "0.5"))
    pages = crawl(max_pages=max_pages, delay_s=delay_s)
    build(pages)
    print(f"Indexed {len(pages)} pages into SQLite.")

