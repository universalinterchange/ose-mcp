import random
from typing import Any

def register_encounters(mcp):
  @mcp.tool()
  def surprise_check(chance: int = 2, in_6: int = 6) -> dict[str, Any]:
    """OSE-ish surprise: default 2-in-6 surprised."""
    r = random.randint(1, int(in_6))
    surprised = r <= int(chance)
    return {"die": int(in_6), "chance": int(chance), "roll": r, "surprised": surprised}

  @mcp.tool()
  def distance_check(environment: str = "dungeon") -> dict[str, Any]:
    """Rough encounter distance generator (tune to taste)."""
    env = (environment or "dungeon").lower()
    if env == "dungeon":
      dist = random.choice([10, 20, 30, 40, 50, 60])  # feet
      unit = "ft"
    else:
      dist = random.choice([30, 60, 90, 120, 180, 240])  # yards
      unit = "yd"
    return {"environment": env, "distance": dist, "unit": unit}

  @mcp.tool()
  def pursuit_evasion(
    terrain: str = "dungeon",
    pursuer_speed: int = 120,
    evader_speed: int = 120,
    headstart: int = 0,
    rounds: int = 6
  ) -> dict[str, Any]:
    """
    Simple chase: each round compare speeds + d6. Track lead. If lead <= 0 -> caught.
    Speeds are abstract; headstart is lead points.
    """
    terr = (terrain or "dungeon").lower()
    lead = int(headstart)
    history = []

    for i in range(1, int(rounds) + 1):
      p = random.randint(1, 6) + (int(pursuer_speed) // 30)
      e = random.randint(1, 6) + (int(evader_speed) // 30)

      delta = e - p
      lead += delta
      history.append({"round": i, "pursuer": p, "evader": e, "delta": delta, "lead": lead})

      if lead <= 0:
        return {"terrain": terr, "caught": True, "round": i, "history": history}

    return {"terrain": terr, "caught": False, "lead": lead, "history": history}

  @mcp.tool()
  def hireling_check(loyalty: int = 7, mod: int = 0) -> dict[str, Any]:
    """2d6 loyalty/morale-ish check: pass if (2d6+mod) <= loyalty."""
    rolls = [random.randint(1, 6), random.randint(1, 6)]
    total = sum(rolls) + int(mod)
    return {"rolls": rolls, "mod": int(mod), "total": total, "loyalty": int(loyalty), "stay": total <= int(loyalty)}

