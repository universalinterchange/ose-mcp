import json
import random
from typing import Any
from ose_mcp.storage.db import connect_campaign as connect

def init_hirelings() -> dict[str, Any]:
  with connect() as con:
    con.executescript("""
    CREATE TABLE IF NOT EXISTS hirelings (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      role TEXT NOT NULL,
      wage_gp_per_day INTEGER NOT NULL DEFAULT 1,
      loyalty INTEGER NOT NULL DEFAULT 7,
      morale INTEGER NOT NULL DEFAULT 7,
      employed INTEGER NOT NULL DEFAULT 1,
      meta_json TEXT NOT NULL DEFAULT '{}'
    """)
  return {"ok": True}

NAMES = ["Aldo","Brina","Cora","Dain","Edda","Fenn","Garr","Hale","Ivo","Jory","Kara","Lenn","Mira","Nash","Orin"]

def register_hirelings(mcp):
  @mcp.tool()
  def hirelings_init() -> dict:
    return init_hirelings()

  @mcp.tool()
  def recruit_hireling(role: str, wage_gp_per_day: int = 1, loyalty: int = 7, morale: int = 7, name: str | None = None) -> dict[str, Any]:
    nm = name or random.choice(NAMES)
    with connect() as con:
      cur = con.execute(
        "INSERT INTO hirelings(name, role, wage_gp_per_day, loyalty, morale) VALUES (?,?,?,?,?)",
        (nm, role, int(wage_gp_per_day), int(loyalty), int(morale)),
      )
    return {"ok": True, "hireling_id": cur.lastrowid, "name": nm, "role": role}

  @mcp.tool()
  def hireling_roster(active_only: bool = True) -> dict[str, Any]:
    with connect() as con:
      if active_only:
        rows = con.execute("SELECT id,name,role,wage_gp_per_day,loyalty,morale FROM hirelings WHERE employed=1 ORDER BY id").fetchall()
      else:
        rows = con.execute("SELECT id,name,role,wage_gp_per_day,loyalty,morale,employed FROM hirelings ORDER BY id").fetchall()
    return {"hirelings": [dict(r) for r in rows]}

  @mcp.tool()
  def pay_wages(days: int = 1) -> dict[str, Any]:
    d = max(1, int(days))
    with connect() as con:
      rows = con.execute("SELECT id,name,wage_gp_per_day FROM hirelings WHERE employed=1").fetchall()
    total = sum(int(r["wage_gp_per_day"]) for r in rows) * d
    return {"ok": True, "days": d, "total_gp": total, "count": len(rows)}

  @mcp.tool()
  def hireling_check(hireling_id: int, kind: str = "loyalty", mod: int = 0) -> dict[str, Any]:
    """2d6 check vs loyalty/morale (<= passes)."""
    rolls = [random.randint(1,6), random.randint(1,6)]
    total = sum(rolls) + int(mod)
    with connect() as con:
      row = con.execute("SELECT name, loyalty, morale FROM hirelings WHERE id=?", (int(hireling_id),)).fetchone()
      if not row:
        raise ValueError("hireling_id not found")
    target = int(row["loyalty"] if kind.lower() == "loyalty" else row["morale"])
    return {"hireling_id": int(hireling_id), "name": row["name"], "kind": kind, "rolls": rolls, "total": total, "target": target, "pass": total <= target}

  @mcp.tool()
  def dismiss_hireling(hireling_id: int) -> dict[str, Any]:
    with connect() as con:
      con.execute("UPDATE hirelings SET employed=0 WHERE id=?", (int(hireling_id),))
    return {"ok": True, "hireling_id": int(hireling_id), "employed": 0}
