import json
from typing import Any
from ose_mcp.storage.db import connect_campaign as connect

DEFAULT_ITEM_WEIGHTS = {
  "Torch": 1,
  "Ration": 1,
  "Waterskin": 1,
  "Rope 50'": 5,
  "Iron Spikes": 1,
}

def register_encumbrance(mcp):
  @mcp.tool()
  def encumbrance_init() -> dict[str, Any]:
    with connect() as con:
      con.executescript("""
      CREATE TABLE IF NOT EXISTS item_weights (
        item TEXT PRIMARY KEY,
        weight INTEGER NOT NULL
      );
      """)
      for k, w in DEFAULT_ITEM_WEIGHTS.items():
        con.execute("INSERT OR IGNORE INTO item_weights(item, weight) VALUES (?,?)", (k, int(w)))
    return {"ok": True}

  @mcp.tool()
  def set_item_weight(item: str, weight: int) -> dict[str, Any]:
    with connect() as con:
      con.execute("INSERT INTO item_weights(item, weight) VALUES (?,?) ON CONFLICT(item) DO UPDATE SET weight=excluded.weight",
            (item, int(weight)))
    return {"ok": True, "item": item, "weight": int(weight)}

  @mcp.tool()
  def encumbrance(pc_id: int, coins_gp: int | None = None, carry_limit: int | None = None) -> dict[str, Any]:
    """
    Compute rough encumbrance:
    - sums item weights from item_weights (unknown items count as 1 each)
    - coins: 100 coins = 1 weight (classic OSR-ish)
    - carry_limit: weight units before "overloaded" (store in meta if provided)
    """
    with connect() as con:
      pc = con.execute("SELECT meta_json FROM pcs WHERE id=?", (int(pc_id),)).fetchone()
      if not pc:
        raise ValueError("pc_id not found")
      meta = json.loads(pc["meta_json"] or "{}")

      if coins_gp is not None:
        meta["coins"] = int(coins_gp)
      coins = int(meta.get("coins", 0))

      if carry_limit is not None:
        meta["carry_limit"] = int(carry_limit)
      limit = int(meta.get("carry_limit", 60))  # default

      rows = con.execute("SELECT item, qty FROM pc_items WHERE pc_id=?", (int(pc_id),)).fetchall()
      total = 0
      details = []
      for r in rows:
        item = r["item"]
        qty = int(r["qty"])
        wrow = con.execute("SELECT weight FROM item_weights WHERE item=?", (item,)).fetchone()
        each = int(wrow["weight"]) if wrow else 1
        w = each * qty
        total += w
        details.append({"item": item, "qty": qty, "each": each, "weight": w})

      coin_w = coins // 100
      total += coin_w

      meta["encumbrance"] = total
      con.execute("UPDATE pcs SET meta_json=? WHERE id=?", (json.dumps(meta), int(pc_id)))

    # Simple movement bands (tune later)
    if total <= limit * 0.5:
      move = 120
    elif total <= limit:
      move = 90
    elif total <= limit * 1.5:
      move = 60
    else:
      move = 30

    return {
      "pc_id": int(pc_id),
      "items_weight": total - coin_w,
      "coins": coins,
      "coins_weight": coin_w,
      "total_weight": total,
      "carry_limit": limit,
      "overloaded": total > limit * 1.5,
      "move_rate": move,
      "details": details
    }

