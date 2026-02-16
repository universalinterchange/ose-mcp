import random
from typing import Any
from ose_mcp.storage.db import connect_campaign as connect

LIKELIHOOD = {
  "impossible": 5,
  "unlikely": 25,
  "even": 50,
  "likely": 75,
  "certain": 95,
}

EVENT_FOCUS = [
  ("PC", 20),
  ("NPC", 20),
  ("Faction", 15),
  ("Location", 15),
  ("Object", 10),
  ("Weather", 5),
  ("Magic", 5),
  ("Random", 10),
]

MEANING_ACTION = [
  "Arrive", "Attack", "Bargain", "Break", "Build", "Change", "Chase", "Discover",
  "Escape", "Expose", "Guard", "Help", "Hide", "Imitate", "Investigate", "Kidnap",
  "Leave", "Mislead", "Open", "Oppose", "Overwhelm", "Protect", "Pursue", "Reveal",
  "Steal", "Summon", "Trade", "Trap", "Travel", "Warn",
]

MEANING_SUBJECT = [
  "A secret", "An ally", "An enemy", "A trap", "A treasure", "A message", "A witness",
  "A betrayal", "A door", "A path", "A bargain", "A curse", "A relic", "A monster",
  "A patrol", "A rival", "A map", "A rumor", "A storm", "A weakness",
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

def register_oracle(mcp):
  @mcp.tool()
  def oracle_set_chaos(chaos: int = 5) -> dict[str, Any]:
    """Set global oracle chaos (1-9). Higher = more twists."""
    c = max(1, min(9, int(chaos)))
    with connect() as con:
      con.executescript("""
      CREATE TABLE IF NOT EXISTS oracle_state (
        id INTEGER PRIMARY KEY CHECK (id=1),
        chaos INTEGER NOT NULL DEFAULT 5
      );
      INSERT OR IGNORE INTO oracle_state (id) VALUES (1);
      """)
      con.execute("UPDATE oracle_state SET chaos=? WHERE id=1", (c,))
    return {"ok": True, "chaos": c}

  def _get_chaos(con) -> int:
    row = con.execute("SELECT chaos FROM oracle_state WHERE id=1").fetchone()
    return int(row["chaos"]) if row else 5

  @mcp.tool()
  def oracle_yesno(question: str, likelihood: str = "even", chaos: int | None = None) -> dict[str, Any]:
    """
    Yes/No oracle with likelihood + chaos, plus AND/BUT twists.

    Returns:
      answer: yes/no
      twist: none/and/but
    """
    likelihood_key = (likelihood or "even").strip().lower()
    base = LIKELIHOOD.get(likelihood_key, 50)

    with connect() as con:
      con.executescript("""
      CREATE TABLE IF NOT EXISTS oracle_state (
        id INTEGER PRIMARY KEY CHECK (id=1),
        chaos INTEGER NOT NULL DEFAULT 5
      );
      INSERT OR IGNORE INTO oracle_state (id) VALUES (1);
      """)
      c = int(chaos) if chaos is not None else _get_chaos(con)

    # Chaos nudges odds slightly toward extremes
    # chaos 5 -> no change, 9 -> stronger swing
    swing = (c - 5) * 2  # -8..+8
    target = max(1, min(99, base + swing))

    roll = random.randint(1, 100)
    answer = "yes" if roll <= target else "no"

    # Twist chance scales with chaos
    twist_roll = random.randint(1, 100)
    twist = "none"
    twist_chance = 5 + c * 3  # 8..32
    if twist_roll <= twist_chance:
      twist = "and" if answer == "yes" else "but"

    return {
      "question": question,
      "likelihood": likelihood_key,
      "chaos": c,
      "target_percent": target,
      "roll": roll,
      "answer": answer,
      "twist": twist,
    }

  @mcp.tool()
  def oracle_event() -> dict[str, Any]:
    """Generate a random event focus + meaning prompts."""
    focus = _weighted_pick(EVENT_FOCUS)
    action = random.choice(MEANING_ACTION)
    subject = random.choice(MEANING_SUBJECT)
    return {"focus": focus, "meaning": {"action": action, "subject": subject}}

  @mcp.tool()
  def oracle_interpret(tags: list[str] | None = None) -> dict[str, Any]:
    """Context-skewed meaning prompts (lightweight)."""
    tags = tags or []
    t = " ".join(tags).lower()

    action = random.choice(MEANING_ACTION)
    subject = random.choice(MEANING_SUBJECT)

    if "dungeon" in t:
      subject = random.choice(["A trap", "A door", "A monster", "A treasure", "A secret", "A path"])
    if "town" in t:
      subject = random.choice(["A bargain", "A rumor", "A rival", "A message", "An ally", "A betrayal"])
    if "wilderness" in t or "travel" in t:
      subject = random.choice(["A storm", "A patrol", "A path", "A lair", "A witness", "A map"])

    return {"tags": tags, "meaning": {"action": action, "subject": subject}}

