import json
import random
from typing import Any
from ose_mcp.storage.db import connect_campaign as connect

def init_tables() -> dict[str, Any]:
  """Create tables for encounter lists (dungeon/wilderness/town complications)."""
  with connect() as con:
    con.executescript("""
    PRAGMA foreign_keys=ON;

    CREATE TABLE IF NOT EXISTS encounter_tables (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      scope TEXT NOT NULL,        -- 'dungeon'|'wilderness'|'town'
      scope_id INTEGER,         -- dungeon_id for dungeon scope; NULL otherwise
      level INTEGER NOT NULL DEFAULT 1,  -- dungeon level / region danger level
      biome TEXT NOT NULL DEFAULT '',  -- e.g. 'forest','swamp','hills','urban'
      name TEXT NOT NULL,
      meta_json TEXT NOT NULL DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS encounter_entries (
      table_id INTEGER NOT NULL,
      entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
      weight INTEGER NOT NULL DEFAULT 1,
      label TEXT NOT NULL,
      data_json TEXT NOT NULL DEFAULT '{}',
      FOREIGN KEY (table_id) REFERENCES encounter_tables(id) ON DELETE CASCADE
    );
    """)
  return {"ok": True}

def _weighted_pick(rows: list[dict[str, Any]]) -> dict[str, Any]:
  total = sum(int(r["weight"]) for r in rows)
  roll = random.randint(1, max(1, total))
  acc = 0
  for r in rows:
    acc += int(r["weight"])
    if roll <= acc:
      return r
  return rows[-1]

def register_tables(mcp):
  @mcp.tool()
  def tables_init() -> dict:
    return init_tables()

  @mcp.tool()
  def create_encounter_table(
    scope: str,
    name: str,
    level: int = 1,
    biome: str = "",
    scope_id: int | None = None,
    meta: dict[str, Any] | None = None
  ) -> dict[str, Any]:
    """
    Create an encounter table.
    scope: 'dungeon' | 'wilderness' | 'town'
    scope_id: dungeon_id when scope='dungeon'
    """
    sc = (scope or "").strip().lower()
    if sc not in ("dungeon", "wilderness", "town"):
      raise ValueError("scope must be 'dungeon', 'wilderness', or 'town'")
    with connect() as con:
      cur = con.execute(
        "INSERT INTO encounter_tables(scope,scope_id,level,biome,name,meta_json) VALUES (?,?,?,?,?,?)",
        (sc, int(scope_id) if scope_id is not None else None, int(level), biome or "", name, json.dumps(meta or {})),
      )
    return {"ok": True, "table_id": cur.lastrowid, "scope": sc, "scope_id": scope_id, "level": int(level), "biome": biome or "", "name": name}

  @mcp.tool()
  def add_encounter_entry(
    table_id: int,
    label: str,
    weight: int = 1,
    data: dict[str, Any] | None = None
  ) -> dict[str, Any]:
    """Add a weighted encounter entry. data can include hd, group_size, notes, link_to_ref, etc."""
    with connect() as con:
      cur = con.execute(
        "INSERT INTO encounter_entries(table_id,weight,label,data_json) VALUES (?,?,?,?)",
        (int(table_id), int(weight), label, json.dumps(data or {})),
      )
    return {"ok": True, "entry_id": cur.lastrowid, "table_id": int(table_id), "label": label, "weight": int(weight), "data": data or {}}

  @mcp.tool()
  def list_encounter_tables(scope: str | None = None, scope_id: int | None = None) -> dict[str, Any]:
    """List encounter tables (optionally filtered)."""
    with connect() as con:
      if scope and scope_id is not None:
        rows = con.execute(
          "SELECT * FROM encounter_tables WHERE lower(scope)=lower(?) AND scope_id=? ORDER BY level, biome, id",
          (scope, int(scope_id)),
        ).fetchall()
      elif scope:
        rows = con.execute(
          "SELECT * FROM encounter_tables WHERE lower(scope)=lower(?) ORDER BY scope_id, level, biome, id",
          (scope,),
        ).fetchall()
      else:
        rows = con.execute("SELECT * FROM encounter_tables ORDER BY scope, scope_id, level, biome, id").fetchall()

    out = []
    for r in rows:
      d = dict(r)
      d["meta"] = json.loads(d.pop("meta_json") or "{}")
      out.append(d)
    return {"tables": out}

  @mcp.tool()
  def list_encounter_entries(table_id: int) -> dict[str, Any]:
    with connect() as con:
      rows = con.execute(
        "SELECT entry_id, weight, label, data_json FROM encounter_entries WHERE table_id=? ORDER BY entry_id",
        (int(table_id),),
      ).fetchall()
    out = []
    for r in rows:
      d = dict(r)
      d["data"] = json.loads(d.pop("data_json") or "{}")
      out.append(d)
    return {"table_id": int(table_id), "entries": out}

  @mcp.tool()
  def random_encounter(
    scope: str,
    level: int = 1,
    biome: str = "",
    scope_id: int | None = None
  ) -> dict[str, Any]:
    """
    Roll an encounter from the best matching table.
    Matching order:
      - exact (scope, scope_id, level, biome)
      - then (scope, scope_id, level, any biome)
      - then (scope, any scope_id, level, biome)
      - then (scope, any scope_id, level, any biome)
    """
    sc = (scope or "").strip().lower()
    b = (biome or "").strip().lower()
    lvl = int(level)

    with connect() as con:
      # candidate tables in priority order
      candidates = []
      params_sets = [
        (sc, scope_id, lvl, b),
        (sc, scope_id, lvl, ""),
        (sc, None,  lvl, b),
        (sc, None,  lvl, ""),
      ]
      for (scc, sid, ll, bb) in params_sets:
        if sid is None:
          rows = con.execute(
            "SELECT * FROM encounter_tables WHERE scope=? AND level=? AND lower(biome)=lower(?) ORDER BY id",
            (scc, ll, bb),
          ).fetchall()
        else:
          rows = con.execute(
            "SELECT * FROM encounter_tables WHERE scope=? AND scope_id=? AND level=? AND lower(biome)=lower(?) ORDER BY id",
            (scc, int(sid), ll, bb),
          ).fetchall()
        for r in rows:
          candidates.append(dict(r))
        if candidates:
          break

      if not candidates:
        return {"ok": False, "error": "no matching encounter table", "scope": sc, "scope_id": scope_id, "level": lvl, "biome": b}

      table = candidates[0]
      entries = con.execute(
        "SELECT entry_id, weight, label, data_json FROM encounter_entries WHERE table_id=?",
        (int(table["id"]),),
      ).fetchall()
      if not entries:
        return {"ok": False, "error": "encounter table has no entries", "table_id": int(table["id"])}

      rows = []
      for e in entries:
        d = dict(e)
        d["data"] = json.loads(d.pop("data_json") or "{}")
        rows.append(d)

      picked = _weighted_pick(rows)

    # return enough structure for your encounter glue tools to use
    return {
      "ok": True,
      "table": {
        "table_id": int(table["id"]),
        "scope": table["scope"],
        "scope_id": table["scope_id"],
        "level": int(table["level"]),
        "biome": table["biome"],
        "name": table["name"],
      },
      "encounter": picked,
    }

  @mcp.tool()
  def seed_basic_dungeon_table(dungeon_id: int, level: int = 1) -> dict[str, Any]:
    """
    Convenience: creates a starter dungeon encounter table with generic OSR entries.
    Swap labels out for real monsters as you like.
    """
    t = create_encounter_table("dungeon", f"Dungeon {dungeon_id} L{level}", level=level, scope_id=dungeon_id)
    tid = int(t["table_id"])
    # generic starter list
    add_encounter_entry(tid, "Goblins (2d6)", 3, {"hd": 1, "group": "2d6"})
    add_encounter_entry(tid, "Skeletons (2d6)", 3, {"hd": 1, "group": "2d6"})
    add_encounter_entry(tid, "Giant Rats (3d6)", 2, {"hd": 1, "group": "3d6"})
    add_encounter_entry(tid, "Bandits (2d6)", 2, {"hd": 1, "group": "2d6"})
    add_encounter_entry(tid, "Ooze/Slime", 1, {"hd": 2, "group": "1"})
    add_encounter_entry(tid, "Patrol (mixed)", 1, {"hd": 2, "group": "1d6+2"})
    return {"ok": True, "table_id": tid}
