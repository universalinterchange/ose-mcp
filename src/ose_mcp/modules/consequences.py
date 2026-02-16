import json
import random
from typing import Any
from ose_mcp.storage.db import connect_campaign as connect

INJURIES = [
  ("Sprained ankle", "move_rate -30 until healed"),
  ("Broken ribs", "disadvantage on strenuous checks (narrative)"),
  ("Concussion", "spell mishap chance +5% (if casting)"),
  ("Deep cut", "max_hp -1 until treated"),
  ("Burns", "reaction rolls -1 with polite folk"),
]

def register_consequences(mcp):
  @mcp.tool()
  def consequences_init() -> dict[str, Any]:
    with connect() as con:
      con.executescript("""
      CREATE TABLE IF NOT EXISTS npc_memory (
        npc_id INTEGER NOT NULL,
        ts TEXT DEFAULT (datetime('now')),
        entry TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS reputation (
        id INTEGER PRIMARY KEY CHECK (id=1),
        fame INTEGER NOT NULL DEFAULT 0,
        notoriety INTEGER NOT NULL DEFAULT 0
      );
      INSERT OR IGNORE INTO reputation (id) VALUES (1);

      CREATE TABLE IF NOT EXISTS injuries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pc_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        effect TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        ts TEXT DEFAULT (datetime('now'))
      );
      """)
    return {"ok": True}

  @mcp.tool()
  def npc_remember(npc_id: int, entry: str) -> dict[str, Any]:
    with connect() as con:
      con.execute("INSERT INTO npc_memory(npc_id, entry) VALUES (?,?)", (int(npc_id), entry))
    return {"ok": True, "npc_id": int(npc_id)}

  @mcp.tool()
  def npc_memory_log(npc_id: int, limit: int = 20) -> dict[str, Any]:
    with connect() as con:
      rows = con.execute("SELECT ts, entry FROM npc_memory WHERE npc_id=? ORDER BY ts DESC LIMIT ?", (int(npc_id), int(limit))).fetchall()
    return {"npc_id": int(npc_id), "memory": [dict(r) for r in rows]}

  @mcp.tool()
  def reputation_adjust(fame: int = 0, notoriety: int = 0) -> dict[str, Any]:
    with connect() as con:
      row = con.execute("SELECT fame, notoriety FROM reputation WHERE id=1").fetchone()
      f = int(row["fame"]) + int(fame)
      n = int(row["notoriety"]) + int(notoriety)
      con.execute("UPDATE reputation SET fame=?, notoriety=? WHERE id=1", (f, n))
    return {"ok": True, "fame": f, "notoriety": n}

  @mcp.tool()
  def reputation_get() -> dict[str, Any]:
    with connect() as con:
      row = con.execute("SELECT fame, notoriety FROM reputation WHERE id=1").fetchone()
    return {"fame": int(row["fame"]), "notoriety": int(row["notoriety"])}

  @mcp.tool()
  def apply_injury(pc_id: int, name: str | None = None, effect: str | None = None) -> dict[str, Any]:
    if name is None or effect is None:
      name, effect = random.choice(INJURIES)
    with connect() as con:
      cur = con.execute("INSERT INTO injuries(pc_id, name, effect) VALUES (?,?,?)", (int(pc_id), name, effect))
    return {"ok": True, "injury_id": cur.lastrowid, "pc_id": int(pc_id), "name": name, "effect": effect}

  @mcp.tool()
  def heal_injury(injury_id: int) -> dict[str, Any]:
    with connect() as con:
      con.execute("UPDATE injuries SET active=0 WHERE id=?", (int(injury_id),))
    return {"ok": True, "injury_id": int(injury_id), "active": 0}

  @mcp.tool()
  def list_injuries(pc_id: int, active_only: bool = True) -> dict[str, Any]:
    with connect() as con:
      if active_only:
        rows = con.execute("SELECT id,name,effect,ts FROM injuries WHERE pc_id=? AND active=1 ORDER BY id DESC", (int(pc_id),)).fetchall()
      else:
        rows = con.execute("SELECT id,name,effect,active,ts FROM injuries WHERE pc_id=? ORDER BY id DESC", (int(pc_id),)).fetchall()
    return {"pc_id": int(pc_id), "injuries": [dict(r) for r in rows]}

