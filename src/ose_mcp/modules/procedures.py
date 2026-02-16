from typing import Any
from ose_mcp.storage.db import connect_campaign as connect

def register_procedures(mcp):
  @mcp.tool()
  def proc_init() -> dict[str, Any]:
    """Initialize procedure state tables."""
    with connect() as con:
      con.executescript("""
      CREATE TABLE IF NOT EXISTS proc_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        dungeon_turn INTEGER NOT NULL DEFAULT 0,
        watch INTEGER NOT NULL DEFAULT 0,
        torch_turns_left INTEGER NOT NULL DEFAULT 0,
        wandering_in_6 INTEGER NOT NULL DEFAULT 6,
        wandering_chance INTEGER NOT NULL DEFAULT 1,
        wandering_every_turns INTEGER NOT NULL DEFAULT 2
      );
      INSERT OR IGNORE INTO proc_state (id) VALUES (1);
      """)
    return {"ok": True}

  @mcp.tool()
  def proc_get() -> dict[str, Any]:
    with connect() as con:
      row = con.execute("SELECT * FROM proc_state WHERE id=1").fetchone()
      return dict(row)

  @mcp.tool()
  def proc_set(
    torch_turns_left: int | None = None,
    wandering_in_6: int | None = None,
    wandering_chance: int | None = None,
    wandering_every_turns: int | None = None,
  ) -> dict[str, Any]:
    """Set exploration procedure knobs."""
    updates = []
    params: list[Any] = []
    if torch_turns_left is not None:
      updates.append("torch_turns_left=?"); params.append(int(torch_turns_left))
    if wandering_in_6 is not None:
      updates.append("wandering_in_6=?"); params.append(int(wandering_in_6))
    if wandering_chance is not None:
      updates.append("wandering_chance=?"); params.append(int(wandering_chance))
    if wandering_every_turns is not None:
      updates.append("wandering_every_turns=?"); params.append(int(wandering_every_turns))

    if not updates:
      return {"ok": True, "note": "no changes"}

    with connect() as con:
      con.execute(f"UPDATE proc_state SET {', '.join(updates)} WHERE id=1", params)
    return {"ok": True, "state": proc_get()}

  @mcp.tool()
  def advance_turn(n: int = 1) -> dict[str, Any]:
    """
    Advance dungeon turns.
    - decrements torch
    - triggers wandering check every N turns (default 2)
    Returns which turns triggered checks and whether a check hit.
    """
    if n < 1:
      raise ValueError("n must be >= 1")

    results = []
    with connect() as con:
      st = con.execute("SELECT * FROM proc_state WHERE id=1").fetchone()
      if not st:
        raise ValueError("proc_state not initialized; run proc_init()")

      turn = int(st["dungeon_turn"])
      torch = int(st["torch_turns_left"])
      in_6 = int(st["wandering_in_6"])
      chance = int(st["wandering_chance"])
      every = int(st["wandering_every_turns"])

      for _ in range(n):
        turn += 1
        if torch > 0:
          torch -= 1

        check = (every > 0 and turn % every == 0)
        if check:
          # emulate 1-in-6 etc without importing mechanics module
          import random
          r = random.randint(1, in_6)
          hit = r <= chance
          results.append({"turn": turn, "wandering_check": True, "die": in_6, "roll": r, "encounter": hit})
        else:
          results.append({"turn": turn, "wandering_check": False})

      con.execute(
        "UPDATE proc_state SET dungeon_turn=?, torch_turns_left=? WHERE id=1",
        (turn, torch),
      )

    return {"advanced": n, "results": results, "state": proc_get()}

  @mcp.tool()
  def time_init() -> dict[str, Any]:
    """Initialize campaign time tracking."""
    with connect() as con:
      con.executescript("""
      CREATE TABLE IF NOT EXISTS time_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        minutes INTEGER NOT NULL DEFAULT 0
      );
      INSERT OR IGNORE INTO time_state (id) VALUES (1);
      """)
    return {"ok": True}

  @mcp.tool()
  def advance_time(hours: float = 1.0) -> dict[str, Any]:
    """Advance campaign time by hours (can be fractional)."""
    if hours <= 0:
      raise ValueError("hours must be > 0")

    add_minutes = int(round(float(hours) * 60.0))
    with connect() as con:
      row = con.execute("SELECT minutes FROM time_state WHERE id=1").fetchone()
      if not row:
        raise ValueError("time_state not initialized; run time_init()")

      minutes = int(row["minutes"]) + add_minutes
      con.execute("UPDATE time_state SET minutes=? WHERE id=1", (minutes,))

    return {"ok": True, "added_minutes": add_minutes, "total_minutes": minutes}


