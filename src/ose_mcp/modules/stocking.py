import random
from typing import Any

ROOM_CONTENTS = [
  ("empty", 40),
  ("monster", 30),
  ("trap", 15),
  ("special", 10),
  ("treasure", 5),
]

ROOM_SIZE = [
  ("small chamber", 35),
  ("large chamber", 25),
  ("hallway", 20),
  ("odd shape", 10),
  ("huge area", 10),
]

EXITS = [
  ("no obvious exits", 10),
  ("1 exit", 35),
  ("2 exits", 30),
  ("3 exits", 15),
  ("4+ exits", 10),
]

HEX_FEATURES = [
  ("ruin", 15),
  ("lair", 10),
  ("village/hamlet", 10),
  ("strange landmark", 15),
  ("hazard", 15),
  ("resource", 10),
  ("nothing notable", 25),
]

def _weighted_pick(items: list[tuple[str, int]]) -> str:
  total = sum(w for _, w in items)
  r = random.randint(1, total)
  acc = 0
  for name, w in items:
    acc += w
    if r <= acc:
      return name
  return items[-1][0]

def register_stocking(mcp):
  @mcp.tool()
  def dungeon_room() -> dict[str, Any]:
    """Generate a quick dungeon room prompt."""
    size = _weighted_pick(ROOM_SIZE)
    exits = _weighted_pick(EXITS)
    contents = _weighted_pick(ROOM_CONTENTS)
    detail = random.choice([
      "damp stone and mildew",
      "fresh drafts and distant echoes",
      "dusty, undisturbed floor",
      "recent scuff marks",
      "faint sulfur smell",
      "sticky cobwebs everywhere",
    ])
    return {
      "size": size,
      "exits": exits,
      "contents": contents,
      "detail": detail,
    }

  @mcp.tool()
  def hex_feature() -> dict[str, Any]:
    """Generate a quick wilderness hex feature prompt."""
    feature = _weighted_pick(HEX_FEATURES)
    twist = random.choice([
      "it’s older than it looks",
      "it’s currently occupied",
      "it’s a decoy / red herring",
      "it has a hidden entrance",
      "it’s cursed or taboo",
      "it’s being fought over",
    ])
    return {"feature": feature, "twist": twist}

