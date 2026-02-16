import json
import random
from typing import Any
from ose_mcp.storage.db import connect_campaign as connect


# -------------------------
# NEW: top-level init function
# -------------------------

def init_oracle(chaos: int = 5) -> dict[str, Any]:
  """
  Initialize oracle state table and optionally set chaos factor.
  Safe to run multiple times.
  """
  ch = max(1, min(9, int(chaos)))

  with connect() as con:

    con.executescript("""
    CREATE TABLE IF NOT EXISTS oracle_state (
      id INTEGER PRIMARY KEY CHECK (id=1),
      chaos INTEGER NOT NULL DEFAULT 5
    );
    """)

    con.execute(
      "INSERT INTO oracle_state(id, chaos) VALUES (1, ?) "
      "ON CONFLICT(id) DO UPDATE SET chaos=excluded.chaos",
      (ch,)
    )

  return {"ok": True, "chaos": ch}


# -------------------------
# Oracle logic helpers
# -------------------------

LIKELIHOOD = {
  "impossible": 5,
  "very unlikely": 15,
  "unlikely": 35,
  "even": 50,
  "likely": 65,
  "very likely": 85,
  "near certain": 95
}


def _get_chaos() -> int:
  with connect() as con:
    row = con.execute(
      "SELECT chaos FROM oracle_state WHERE id=1"
    ).fetchone()

  return int(row["chaos"]) if row else 5


def _oracle_roll(likelihood: str) -> dict:
  base = LIKELIHOOD.get(likelihood.lower(), 50)
  chaos = _get_chaos()
  roll = random.randint(1, 100)
  modified = roll + (chaos - 5) * 5
  yes = modified <= base
  exceptional = (
    roll <= base * 0.2 or
    roll >= 100 - (100 - base) * 0.2
  )

  if exceptional and yes:
    answer = "Yes, and..."
  elif exceptional and not yes:
    answer = "No, and..."
  elif yes:
    answer = "Yes"
  else:
    answer = "No"

  return {
    "answer": answer,
    "roll": roll,
    "modified": modified,
    "chaos": chaos,
    "likelihood": likelihood
  }


# -------------------------
# MCP registration
# -------------------------

def register_oracle(mcp):

  # Tool: oracle_init
  @mcp.tool()
  def oracle_init(chaos: int = 5) -> dict[str, Any]:
    """
    Initialize oracle system and set chaos factor.
    """
    return init_oracle(chaos)

  # Tool: oracle_set_chaos
  @mcp.tool()
  def oracle_set_chaos(chaos: int) -> dict[str, Any]:
    """Set chaos factor (1-9)."""
    ch = max(1, min(9, int(chaos)))
    with connect() as con:
      con.execute(
        "INSERT INTO oracle_state(id, chaos) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET chaos=excluded.chaos",
        (ch,)
      )

    return {"ok": True, "chaos": ch}


  # Tool: oracle_yesno
  @mcp.tool()
  def oracle_yesno(question: str, likelihood: str = "even") -> dict[str, Any]:
    """Answer a yes/no question using likelihood and chaos factor."""
    result = _oracle_roll(likelihood)
    result["question"] = question
    return result


  # Tool: oracle_event
  @mcp.tool()
  def oracle_event() -> dict[str, Any]:
    """Generate a random oracle event prompt (verb+noun)."""
    verbs = [
      "Attack", "Defend", "Move", "Investigate",
      "Reveal", "Transform", "Delay", "Protect"
    ]

    nouns = [
      "Enemy", "Friend", "Location", "Item",
      "Secret", "Faction", "Leader", "Danger"
    ]

    return {
      "verb": random.choice(verbs),
      "noun": random.choice(nouns)
    }

