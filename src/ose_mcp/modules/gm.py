import random
from typing import Any
from ose_mcp.storage.db import connect_campaign as connect

def register_gm(mcp):
  @mcp.tool()
  def gm_step(
    mode: str = "dungeon",
    dungeon_id: int | None = None,
    room_key: str | None = None,
    hex_key: str | None = None,
    advance_turns: int = 1
  ) -> dict[str, Any]:
    """
    One-button solo loop:
    - dungeon: advances turns + wandering check, returns next room prompt
    - travel: returns travel day encounter + weather
    - town: returns rumor or event prompt
    """
    md = (mode or "dungeon").lower()

    # lazy import tools by calling DB-backed state directly is brittle;
    # instead, we do minimal orchestration and return suggested next tool calls.
    out: dict[str, Any] = {"mode": md, "suggestions": []}

    if md == "dungeon":
      # Advance turns by directly reading proc_state if present
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
        st = con.execute("SELECT * FROM proc_state WHERE id=1").fetchone()
        turn = int(st["dungeon_turn"])
        torch = int(st["torch_turns_left"])
        in_6 = int(st["wandering_in_6"])
        chance = int(st["wandering_chance"])
        every = int(st["wandering_every_turns"])

        results = []
        for _ in range(max(1, int(advance_turns))):
          turn += 1
          if torch > 0:
            torch -= 1

          check = (every > 0 and turn % every == 0)
          if check:
            r = random.randint(1, in_6)
            hit = r <= chance
            results.append({"turn": turn, "wandering_check": True, "roll": r, "die": in_6, "encounter": hit})
          else:
            results.append({"turn": turn, "wandering_check": False})

        con.execute("UPDATE proc_state SET dungeon_turn=?, torch_turns_left=? WHERE id=1", (turn, torch))

      out["turns"] = results
      # If any encounter triggered, suggest encounter resolution calls
      if any(r.get("encounter") for r in results):
        out["event"] = "wandering_encounter"
        out["suggestions"] += [
          "surprise_check()",
          "distance_check(environment='dungeon')",
          "reaction_roll()",
          "morale_check(morale=7)",
        ]
        if dungeon_id is not None:
          out["suggestions"].insert(0, f"random_encounter(scope='dungeon', scope_id={int(dungeon_id)}, level=1)")
        return out

      # Otherwise suggest room generation / persistence
      if dungeon_id is None:
        out["event"] = "need_dungeon"
        out["suggestions"].append("create_dungeon('Your Dungeon Name')")
        return out

      rk = (room_key or f"R{turn}").upper()
      out["event"] = "next_room"
      out["room_key"] = rk
      out["suggestions"].append(f"enter_room({int(dungeon_id)}, '{rk}')")
      out["suggestions"].append("dungeon_room()  # if you want a non-persistent prompt too")
      return out

      if md == "travel":
        out["event"] = "travel_day"
        out["suggestions"] += [
            "weather_roll()",
            "travel(days=1, terrain='plains', pace='normal')",
            "distance_check(environment='wilderness')",
            "reaction_roll()",
        ]
        if hex_key:
          hk = hex_key.strip().upper()
          out["suggestions"].insert(0, f"encounter_for_hex('{hk}')")  # Option A helper
          # Or if you didn't add encounter_for_hex, use:
          # out["suggestions"].insert(0, "random_encounter(scope='wilderness', level=1, biome='plains')")
        else:
          out["suggestions"].insert(0, "random_encounter(scope='wilderness', level=1, biome='plains')")
        return out

    if md == "town":
      out["event"] = "town_pressure"
      out["suggestions"] += [
        "get_rumor()",
        "oracle_event()",
        "oracle_yesno('Does trouble find us today?', likelihood='even')",
        "faction_turn(weeks=1)",
      ]
      return out

    # fallback
    out["event"] = "unknown_mode"
    out["suggestions"].append("oracle_event()")
    return out

