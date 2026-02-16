import json
from typing import Any
from ose_mcp.storage.db import connect_campaign as connect

# default burn rates in dungeon turns (10 min each)
DEFAULT_LIGHT = {
  "Torch": 6,    # 1 hour = 6 turns
  "Lantern": 24,   # 4 hours = 24 turns (example; tune)
  "Candle": 3,
}

def register_light(mcp):
  @mcp.tool()
  def light_init() -> dict[str, Any]:
    with connect() as con:
      con.executescript("""
      CREATE TABLE IF NOT EXISTS light_rules (
        item TEXT PRIMARY KEY,
        turns INTEGER NOT NULL
      );
      CREATE TABLE IF NOT EXISTS light_state (
        pc_id INTEGER PRIMARY KEY,
        active_item TEXT,
        turns_left INTEGER NOT NULL DEFAULT 0
      );
      """)
      for item, t in DEFAULT_LIGHT.items():
        con.execute("INSERT OR IGNORE INTO light_rules(item, turns) VALUES (?,?)", (item, int(t)))
    return {"ok": True}

  @mcp.tool()
  def light_equip(pc_id: int, item: str) -> dict[str, Any]:
    """Set active light source; consumes 1 from inventory when first equipped if it’s a consumable."""
    with connect() as con:
      rule = con.execute("SELECT turns FROM light_rules WHERE item=?", (item,)).fetchone()
      if not rule:
        raise ValueError("unknown light item; add with set_item_weight + light_rules insert later if needed")
      turns = int(rule["turns"])

      # consume 1 from inventory
      row = con.execute("SELECT qty FROM pc_items WHERE pc_id=? AND item=?", (int(pc_id), item)).fetchone()
      have = int(row["qty"]) if row else 0
      if have <= 0:
        raise ValueError(f"pc has no {item}")

      new_qty = have - 1
      if new_qty == 0:
        con.execute("DELETE FROM pc_items WHERE pc_id=? AND item=?", (int(pc_id), item))
      else:
        con.execute("UPDATE pc_items SET qty=? WHERE pc_id=? AND item=?", (new_qty, int(pc_id), item))

      con.execute(
        "INSERT INTO light_state(pc_id, active_item, turns_left) VALUES (?,?,?) "
        "ON CONFLICT(pc_id) DO UPDATE SET active_item=excluded.active_item, turns_left=excluded.turns_left",
        (int(pc_id), item, turns),
      )
    return {"ok": True, "pc_id": int(pc_id), "active_item": item, "turns_left": turns}

  @mcp.tool()
  def light_tick(pc_id: int, turns: int = 1) -> dict[str, Any]:
    """Burn active light by N dungeon turns; if expires, clears active."""
    t = max(1, int(turns))
    with connect() as con:
      st = con.execute("SELECT active_item, turns_left FROM light_state WHERE pc_id=?", (int(pc_id),)).fetchone()
      if not st or not st["active_item"]:
        return {"ok": True, "pc_id": int(pc_id), "active_item": None, "turns_left": 0}

      left = int(st["turns_left"]) - t
      if left <= 0:
        con.execute("UPDATE light_state SET active_item=NULL, turns_left=0 WHERE pc_id=?", (int(pc_id),))
        return {"ok": True, "pc_id": int(pc_id), "expired": True, "active_item": None, "turns_left": 0}

      con.execute("UPDATE light_state SET turns_left=? WHERE pc_id=?", (left, int(pc_id)))
    return {"ok": True, "pc_id": int(pc_id), "active_item": st["active_item"], "turns_left": left}

  @mcp.tool()
  def light_status(pc_id: int) -> dict[str, Any]:
    with connect() as con:
      st = con.execute("SELECT active_item, turns_left FROM light_state WHERE pc_id=?", (int(pc_id),)).fetchone()
    if not st:
      return {"pc_id": int(pc_id), "active_item": None, "turns_left": 0}
    return {"pc_id": int(pc_id), "active_item": st["active_item"], "turns_left": int(st["turns_left"])}
