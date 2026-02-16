import random
from typing import Any

def register_loot(mcp):
  @mcp.tool()
  def treasure_roll(kind: str = "individual", hd: int = 1, dungeon_level: int = 1) -> dict[str, Any]:
    """
    Simple tunable treasure roller (not rules-text exact).
    Use it GM-less; adjust weights later.
    """
    k = (kind or "individual").lower()
    hd = max(1, int(hd))
    dl = max(1, int(dungeon_level))

    coins = 0
    gems = 0
    jewelry = 0
    magic = 0

    if k == "individual":
      coins = random.randint(0, 50) * hd
      gems = 1 if random.randint(1, 100) <= (5 + dl) else 0
      magic = 1 if random.randint(1, 100) <= max(1, dl - 1) else 0
    else:
      coins = random.randint(50, 300) * hd * dl
      gems = random.randint(0, 3) if random.randint(1, 100) <= (25 + dl * 2) else 0
      jewelry = random.randint(0, 2) if random.randint(1, 100) <= (15 + dl) else 0
      magic = 1 if random.randint(1, 100) <= (10 + dl * 2) else 0

    return {
      "kind": k,
      "hd": hd,
      "dungeon_level": dl,
      "treasure": {
        "coins_gp": coins,
        "gems": gems,
        "jewelry": jewelry,
        "magic_items": magic
      }
    }

