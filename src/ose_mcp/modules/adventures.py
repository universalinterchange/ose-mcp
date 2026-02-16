import random
from typing import Any
from ose_mcp.storage.db import connect_campaign as connect

def init_adventures() -> dict[str, Any]:
  with connect() as con:
    con.executescript("""
    CREATE TABLE IF NOT EXISTS quests (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'open',
      details TEXT NOT NULL,
      reward TEXT NOT NULL DEFAULT '',
      linked_site_id INTEGER,
      created_ts TEXT DEFAULT (datetime('now'))
    );
    """)
  return {"ok": True}

PATRONS = ["a desperate widow", "a minor noble", "a worried priest", "a smug merchant", "a nervous guild rep"]
PROBLEMS = ["missing person", "stolen relic", "bandit threat", "haunted ruin", "monster lair", "political sabotage"]
REWARDS = ["coin", "land deed", "favor", "rare map", "magic trinket", "access to training"]
TWISTS = ["a rival party interferes", "the patron lies", "it’s a trap", "the target is innocent", "time is running out"]

def register_adventures(mcp):
  @mcp.tool()
  def adventures_init() -> dict:
    """Initialize adventures/quests tables (safe to run multiple times)."""
    return init_adventures()

  @mcp.tool()
  def quest_generate(theme: str = "generic", link_site_id: int | None = None) -> dict[str, Any]:
    """Generate Quest and return ID"""
    patron = random.choice(PATRONS)
    problem = random.choice(PROBLEMS)
    reward = random.choice(REWARDS)
    twist = random.choice(TWISTS)

    title = f"{problem.title()} for {patron}"
    details = f"Patron: {patron}. Problem: {problem}. Twist: {twist}."
    with connect() as con:
      cur = con.execute(
        "INSERT INTO quests(title, details, reward, linked_site_id) VALUES (?,?,?,?)",
        (title, details, reward, int(link_site_id) if link_site_id is not None else None),
      )
    return {"ok": True, "quest_id": cur.lastrowid, "title": title, "details": details, "reward": reward}

  @mcp.tool()
  def quest_list(status: str = "open") -> dict[str, Any]:
    """List Quests with ID"""
    st = (status or "open").lower()
    with connect() as con:
      rows = con.execute("SELECT id,title,status,reward,linked_site_id,created_ts FROM quests WHERE lower(status)=lower(?) ORDER BY id DESC", (st,)).fetchall()
    return {"quests": [dict(r) for r in rows]}

  @mcp.tool()
  def quest_set_status(quest_id: int, status: str) -> dict[str, Any]:
    """Update Quest by ID"""
    with connect() as con:
      con.execute("UPDATE quests SET status=? WHERE id=?", (status, int(quest_id)))
    return {"ok": True, "quest_id": int(quest_id), "status": status}
