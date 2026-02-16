import random
from typing import Any
from ose_mcp.storage.db import connect_campaign as connect

def register_travel(mcp):
  @mcp.tool()
  def weather_roll(region: str = "temperate", season: str = "spring") -> dict[str, Any]:
    reg = (region or "temperate").lower()
    sea = (season or "spring").lower()
    base = ["clear", "overcast", "rain", "wind", "storm"]
    if sea in ("winter",):
      base += ["snow", "freezing rain"]
    if reg in ("desert",):
      base = ["clear", "hot wind", "dust", "heatwave", "sandstorm"]
    result = random.choice(base)
    return {"region": reg, "season": sea, "weather": result}

  def _consume_item(con, pc_id: int, item: str, qty: int) -> int:
    row = con.execute("SELECT qty FROM pc_items WHERE pc_id=? AND item=?", (int(pc_id), item)).fetchone()
    have = int(row["qty"]) if row else 0
    new_qty = have - qty
    if new_qty <= 0:
      con.execute("DELETE FROM pc_items WHERE pc_id=? AND item=?", (int(pc_id), item))
      return 0
    con.execute(
      "INSERT INTO pc_items(pc_id,item,qty) VALUES (?,?,?) "
      "ON CONFLICT(pc_id,item) DO UPDATE SET qty=excluded.qty",
      (int(pc_id), item, new_qty),
    )
    return new_qty

  @mcp.tool()
  def consume_rations(pc_id: int, days: int = 1, item_name: str = "Ration") -> dict[str, Any]:
    """Consume rations from inventory."""
    d = max(1, int(days))
    with connect() as con:
      con.executescript("""
      CREATE TABLE IF NOT EXISTS pc_items (
        pc_id INTEGER NOT NULL,
        item TEXT NOT NULL,
        qty INTEGER NOT NULL,
        PRIMARY KEY (pc_id, item)
      );
      """)
      new_qty = _consume_item(con, pc_id, item_name, d)
    return {"ok": True, "pc_id": int(pc_id), "item": item_name, "consumed": d, "qty": new_qty}

  @mcp.tool()
  def travel(days: int = 1, terrain: str = "plains", pace: str = "normal", encounter_in_6: int = 6, encounter_chance: int = 1) -> dict[str, Any]:
    """
    Travel procedure:
    - rolls 1-in-6 encounter per day by default (tunable)
    - returns weather + encounter results
    """
    d = max(1, int(days))
    terr = (terrain or "plains").lower()
    pace = (pace or "normal").lower()

    enc = []
    for i in range(1, d + 1):
      r = random.randint(1, int(encounter_in_6))
      hit = r <= int(encounter_chance)
      enc.append({"day": i, "roll": r, "die": int(encounter_in_6), "encounter": hit})

    weather = weather_roll("temperate", "spring")["weather"]
    return {"ok": True, "days": d, "terrain": terr, "pace": pace, "weather": weather, "encounters": enc}
