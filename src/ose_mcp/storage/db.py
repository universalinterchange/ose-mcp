import os
import sqlite3
from pathlib import Path

def _ensure_parent(p: Path) -> Path:
  p.parent.mkdir(parents=True, exist_ok=True)
  return p

def campaign_db_path() -> Path:
  # default campaign db
  return _ensure_parent(Path(os.environ.get("OSE_MCP_CAMPAIGN_DB", "data/campaign.sqlite")))

def refs_db_path() -> Path:
  # default refs db
  return _ensure_parent(Path(os.environ.get("OSE_MCP_REFS_DB", "data/refs.sqlite")))

def connect_campaign() -> sqlite3.Connection:
  con = sqlite3.connect(campaign_db_path())
  con.row_factory = sqlite3.Row
  return con

def connect_refs() -> sqlite3.Connection:
  con = sqlite3.connect(refs_db_path())
  con.row_factory = sqlite3.Row
  return con

