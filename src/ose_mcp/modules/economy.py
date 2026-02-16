import json
from typing import Any
from ose_mcp.storage.db import connect_campaign as connect

def register_economy(mcp):
  @mcp.tool()
  def economy_init() -> dict[str, Any]:
    with connect() as con:
      con.executescript("""
      CREATE TABLE IF NOT EXISTS market_items (
        name TEXT PRIMARY KEY,
        base_price_gp INTEGER NOT NULL,
        tags TEXT NOT NULL DEFAULT ''
      );
      """)
    return {"ok": True}

  @mcp.tool()
  def set_market_item(name: str, base_price_gp: int, tags: list[str] | None = None) -> dict[str, Any]:
    t = ",".join(tags or [])
    with connect() as con:
      con.execute(
        "INSERT INTO market_items(name, base_price_gp, tags) VALUES (?,?,?) "
        "ON CONFLICT(name) DO UPDATE SET base_price_gp=excluded.base_price_gp, tags=excluded.tags",
        (name, int(base_price_gp), t),
      )
    return {"ok": True, "name": name, "base_price_gp": int(base_price_gp), "tags": tags or []}

  @mcp.tool()
  def buy_item(pc_id: int, item: str, qty: int = 1, price_mod: float = 1.0) -> dict[str, Any]:
    q = max(1, int(qty))
    with connect() as con:
      m = con.execute("SELECT base_price_gp FROM market_items WHERE name=?", (item,)).fetchone()
      if not m:
        raise ValueError("unknown market item; set_market_item first")
      base = int(m["base_price_gp"])
      cost = int(round(base * float(price_mod))) * q

      row = con.execute("SELECT meta_json FROM pcs WHERE id=?", (int(pc_id),)).fetchone()
      if not row:
        raise ValueError("pc_id not found")
      meta = json.loads(row["meta_json"] or "{}")
      coins = int(meta.get("coins", 0))
      if coins < cost:
        return {"ok": False, "error": "not enough coins", "need": cost, "have": coins}

      meta["coins"] = coins - cost
      con.execute("UPDATE pcs SET meta_json=? WHERE id=?", (json.dumps(meta), int(pc_id)))

      # add inventory
      con.execute(
        "INSERT INTO pc_items(pc_id,item,qty) VALUES (?,?,?) "
        "ON CONFLICT(pc_id,item) DO UPDATE SET qty=pc_items.qty + excluded.qty",
        (int(pc_id), item, q),
      )
    return {"ok": True, "pc_id": int(pc_id), "item": item, "qty": q, "cost_gp": cost, "coins_left": meta["coins"]}

  @mcp.tool()
  def sell_item(pc_id: int, item: str, qty: int = 1, sell_rate: float = 0.5) -> dict[str, Any]:
    q = max(1, int(qty))
    with connect() as con:
      m = con.execute("SELECT base_price_gp FROM market_items WHERE name=?", (item,)).fetchone()
      base = int(m["base_price_gp"]) if m else 0
      revenue = int(round(base * float(sell_rate))) * q

      inv = con.execute("SELECT qty FROM pc_items WHERE pc_id=? AND item=?", (int(pc_id), item)).fetchone()
      have = int(inv["qty"]) if inv else 0
      if have < q:
        return {"ok": False, "error": "not enough items to sell", "have": have, "need": q}

      new_qty = have - q
      if new_qty == 0:
        con.execute("DELETE FROM pc_items WHERE pc_id=? AND item=?", (int(pc_id), item))
      else:
        con.execute("UPDATE pc_items SET qty=? WHERE pc_id=? AND item=?", (new_qty, int(pc_id), item))

      row = con.execute("SELECT meta_json FROM pcs WHERE id=?", (int(pc_id),)).fetchone()
      meta = json.loads(row["meta_json"] or "{}")
      meta["coins"] = int(meta.get("coins", 0)) + revenue
      con.execute("UPDATE pcs SET meta_json=? WHERE id=?", (json.dumps(meta), int(pc_id)))

    return {"ok": True, "pc_id": int(pc_id), "item": item, "sold": q, "revenue_gp": revenue, "coins_now": meta["coins"]}

