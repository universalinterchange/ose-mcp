import json
from typing import Any
from ose_mcp.storage.db import connect_campaign as connect
from ose_mcp.storage.db import connect_refs

def register_state(mcp):
  @mcp.tool()
  def state_init() -> dict[str, Any]:
    """Initialize state tables."""
    with connect() as con:
      con.executescript("""
      CREATE TABLE IF NOT EXISTS pcs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        klass TEXT,
        hp INTEGER,
        max_hp INTEGER,
        meta_json TEXT NOT NULL DEFAULT '{}'
      );

      CREATE TABLE IF NOT EXISTS pc_items (
        pc_id INTEGER NOT NULL,
        item TEXT NOT NULL,
        qty INTEGER NOT NULL,
        PRIMARY KEY (pc_id, item),
        FOREIGN KEY (pc_id) REFERENCES pcs(id) ON DELETE CASCADE
      );

      CREATE TABLE IF NOT EXISTS pc_conditions (
        pc_id INTEGER NOT NULL,
        condition TEXT NOT NULL,
        on_off INTEGER NOT NULL,
        PRIMARY KEY (pc_id, condition),
        FOREIGN KEY (pc_id) REFERENCES pcs(id) ON DELETE CASCADE
      );

      CREATE TABLE IF NOT EXISTS clocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        filled INTEGER NOT NULL DEFAULT 0,
        segments INTEGER NOT NULL DEFAULT 6,
        meta_json TEXT NOT NULL DEFAULT '{}'
      );

      CREATE TABLE IF NOT EXISTS log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT DEFAULT (datetime('now')),
        tag TEXT,
        entry TEXT NOT NULL
      );
      """)
    return {"ok": True}

  @mcp.tool()
  def create_pc(name: str, klass: str = "", hp: int = 1, max_hp: int = 1, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = meta or {}
    with connect() as con:
      cur = con.execute(
        "INSERT INTO pcs (name, klass, hp, max_hp, meta_json) VALUES (?,?,?,?,?)",
        (name, klass, int(hp), int(max_hp), json.dumps(meta)),
      )
      return {"pc_id": cur.lastrowid, "name": name, "klass": klass, "hp": hp, "max_hp": max_hp, "meta": meta}

  @mcp.tool()
  def get_pc(pc_id: int) -> dict[str, Any]:
    with connect() as con:
      row = con.execute("SELECT * FROM pcs WHERE id=?", (int(pc_id),)).fetchone()
      if not row:
        raise ValueError("pc_id not found")
      d = dict(row)
      d["meta"] = json.loads(d.pop("meta_json") or "{}")
      items = con.execute("SELECT item, qty FROM pc_items WHERE pc_id=?", (int(pc_id),)).fetchall()
      conds = con.execute("SELECT condition, on_off FROM pc_conditions WHERE pc_id=?", (int(pc_id),)).fetchall()
      d["items"] = [dict(r) for r in items]
      d["conditions"] = [{"condition": r["condition"], "on": bool(r["on_off"])} for r in conds]
      return d

  @mcp.tool()
  def apply_damage(pc_id: int, amount: int) -> dict[str, Any]:
    with connect() as con:
      row = con.execute("SELECT hp, max_hp FROM pcs WHERE id=?", (int(pc_id),)).fetchone()
      if not row:
        raise ValueError("pc_id not found")
      new_hp = max(0, int(row["hp"]) - int(amount))
      con.execute("UPDATE pcs SET hp=? WHERE id=?", (new_hp, int(pc_id)))
      return {"pc_id": pc_id, "damage": int(amount), "hp": new_hp, "max_hp": int(row["max_hp"])}

  @mcp.tool()
  def heal(pc_id: int, amount: int) -> dict[str, Any]:
    with connect() as con:
      row = con.execute("SELECT hp, max_hp FROM pcs WHERE id=?", (int(pc_id),)).fetchone()
      if not row:
        raise ValueError("pc_id not found")
      new_hp = min(int(row["max_hp"]), int(row["hp"]) + int(amount))
      con.execute("UPDATE pcs SET hp=? WHERE id=?", (new_hp, int(pc_id)))
      return {"pc_id": pc_id, "healed": int(amount), "hp": new_hp, "max_hp": int(row["max_hp"])}

  @mcp.tool()
  def add_item(pc_id: int, item: str, qty: int = 1) -> dict[str, Any]:
    if qty == 0:
      return {"ok": True, "note": "qty=0 no change"}
    with connect() as con:
      cur = con.execute("SELECT qty FROM pc_items WHERE pc_id=? AND item=?", (int(pc_id), item)).fetchone()
      new_qty = int(qty) + (int(cur["qty"]) if cur else 0)
      if new_qty <= 0:
        con.execute("DELETE FROM pc_items WHERE pc_id=? AND item=?", (int(pc_id), item))
        return {"pc_id": pc_id, "item": item, "qty": 0, "removed": True}
      con.execute(
        "INSERT INTO pc_items(pc_id,item,qty) VALUES (?,?,?) "
        "ON CONFLICT(pc_id,item) DO UPDATE SET qty=excluded.qty",
        (int(pc_id), item, new_qty),
      )
      return {"pc_id": pc_id, "item": item, "qty": new_qty}

  @mcp.tool()
  def set_condition(pc_id: int, condition: str, on: bool = True) -> dict[str, Any]:
    with connect() as con:
      con.execute(
        "INSERT INTO pc_conditions(pc_id,condition,on_off) VALUES (?,?,?) "
        "ON CONFLICT(pc_id,condition) DO UPDATE SET on_off=excluded.on_off",
        (int(pc_id), condition, 1 if on else 0),
      )
    return {"pc_id": pc_id, "condition": condition, "on": bool(on)}

  @mcp.tool()
  def create_clock(name: str, segments: int = 6, filled: int = 0, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = meta or {}
    with connect() as con:
      cur = con.execute(
        "INSERT INTO clocks(name,filled,segments,meta_json) VALUES (?,?,?,?)",
        (name, int(filled), int(segments), json.dumps(meta)),
      )
      return {"clock_id": cur.lastrowid, "name": name, "filled": int(filled), "segments": int(segments), "meta": meta}

  @mcp.tool()
  def tick_clock(clock_id: int, delta: int = 1) -> dict[str, Any]:
    with connect() as con:
      row = con.execute("SELECT filled, segments FROM clocks WHERE id=?", (int(clock_id),)).fetchone()
      if not row:
        raise ValueError("clock_id not found")
      filled = max(0, min(int(row["segments"]), int(row["filled"]) + int(delta)))
      con.execute("UPDATE clocks SET filled=? WHERE id=?", (filled, int(clock_id)))
      return {"clock_id": clock_id, "filled": filled, "segments": int(row["segments"]), "complete": filled >= int(row["segments"])}

  @mcp.tool()
  def log_event(entry: str, tag: str = "") -> dict[str, Any]:
    with connect() as con:
      cur = con.execute("INSERT INTO log (tag, entry) VALUES (?,?)", (tag, entry))
      return {"log_id": cur.lastrowid, "tag": tag, "entry": entry}

  @mcp.tool()
  def recent_log(tag: str = "", limit: int = 10) -> dict[str, Any]:
    with connect() as con:
      if tag:
        rows = con.execute("SELECT * FROM log WHERE tag=? ORDER BY id DESC LIMIT ?", (tag, int(limit))).fetchall()
      else:
        rows = con.execute("SELECT * FROM log ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
    return {"items": [dict(r) for r in rows]}

  @mcp.tool()
  def delete_pc(pc_id: int, confirm: bool = False) -> dict[str, Any]:
    """
    Delete a player character and all associated items and conditions.
    Requires confirm=True to prevent accidents.
    """
    if not confirm:
      return {
        "ok": False,
        "error": "Deletion requires confirm=True",
        "pc_id": pc_id
      }

    with connect() as con:
      row = con.execute(
        "SELECT name FROM pcs WHERE id=?",
        (int(pc_id),)
      ).fetchone()

      if not row:
        return {
          "ok": False,
          "error": "pc_id not found",
          "pc_id": pc_id
        }

      name = row["name"]

      con.execute(
        "DELETE FROM pcs WHERE id=?",
        (int(pc_id),)
      )

    return {
      "ok": True,
      "deleted_pc_id": pc_id,
      "name": name
    }

  @mcp.tool()
  def list_pcs() -> dict[str, Any]:
    """List all PCs (basic info)."""
    with connect() as con:
      rows = con.execute(
        "SELECT id, name, klass, hp, max_hp FROM pcs ORDER BY id ASC"
      ).fetchall()
    return {"pcs": [dict(r) for r in rows]}

  @mcp.tool()
  def rename_pc(pc_id: int, new_name: str, new_klass: str | None = None) -> dict[str, Any]:
    """Rename a PC (and optionally update class)."""
    new_name = new_name.strip()
    if not new_name:
      raise ValueError("new_name cannot be empty")

    with connect() as con:
      row = con.execute(
        "SELECT id, name, klass FROM pcs WHERE id=?",
        (int(pc_id),),
      ).fetchone()
      if not row:
        raise ValueError("pc_id not found")

      if new_klass is None:
        con.execute(
          "UPDATE pcs SET name=? WHERE id=?",
          (new_name, int(pc_id)),
        )
      else:
        con.execute(
          "UPDATE pcs SET name=?, klass=? WHERE id=?",
          (new_name, new_klass, int(pc_id)),
        )

    return {
      "ok": True,
      "pc_id": pc_id,
      "old_name": row["name"],
      "new_name": new_name,
      "old_klass": row["klass"],
      "new_klass": (row["klass"] if new_klass is None else new_klass),
    }

  @mcp.tool()
  def get_pc_by_name(name: str, exact: bool = False) -> dict[str, Any]:
    """
    Get PC(s) by name.

    If exact=False (default), performs case-insensitive partial match.
    If exact=True, requires exact match (case-insensitive).
    Returns full PC info including items and conditions.
    """
    name = name.strip()
    if not name:
      raise ValueError("name cannot be empty")

    with connect() as con:

      if exact:
        rows = con.execute(
          "SELECT * FROM pcs WHERE lower(name) = lower(?)",
          (name,),
        ).fetchall()
      else:
        rows = con.execute(
          "SELECT * FROM pcs WHERE lower(name) LIKE lower(?)",
          (f"%{name}%",),
        ).fetchall()

      results = []

      for row in rows:
        pc = dict(row)
        pc["meta"] = json.loads(pc.pop("meta_json") or "{}")

        items = con.execute(
          "SELECT item, qty FROM pc_items WHERE pc_id=?",
          (pc["id"],),
        ).fetchall()

        conds = con.execute(
          "SELECT condition, on_off FROM pc_conditions WHERE pc_id=?",
          (pc["id"],),
        ).fetchall()

        pc["items"] = [dict(r) for r in items]

        pc["conditions"] = [
          {
            "condition": r["condition"],
            "on": bool(r["on_off"])
          }
          for r in conds
        ]

        results.append(pc)

    return {
      "query": name,
      "exact": exact,
      "count": len(results),
      "pcs": results,
    }

  @mcp.tool()
  def award_xp(pc_id: int, amount: int) -> dict[str, Any]:
    """Add XP to a PC (stored in meta.xp)."""
    with connect() as con:
      row = con.execute("SELECT meta_json FROM pcs WHERE id=?", (int(pc_id),)).fetchone()
      if not row:
        raise ValueError("pc_id not found")

      meta = json.loads(row["meta_json"] or "{}")
      meta["xp"] = int(meta.get("xp", 0)) + int(amount)

      con.execute("UPDATE pcs SET meta_json=? WHERE id=?", (json.dumps(meta), int(pc_id)))

    return {"ok": True, "pc_id": pc_id, "awarded": int(amount), "xp": meta["xp"]}

  @mcp.tool()
  def long_rest(pc_id: int, clear_conditions: bool = True) -> dict[str, Any]:
    """Long rest: heal to max HP, optionally clear common temporary conditions."""
    with connect() as con:
      row = con.execute("SELECT hp, max_hp FROM pcs WHERE id=?", (int(pc_id),)).fetchone()
      if not row:
        raise ValueError("pc_id not found")

      con.execute("UPDATE pcs SET hp=? WHERE id=?", (int(row["max_hp"]), int(pc_id)))

      cleared = []
      if clear_conditions:
        # Adjust this list to your taste
        to_clear = {"fatigued", "shaken", "frightened", "nauseated", "poisoned"}  # example set
        rows = con.execute("SELECT condition FROM pc_conditions WHERE pc_id=? AND on_off=1", (int(pc_id),)).fetchall()
        for r in rows:
          c = r["condition"]
          if c.lower() in to_clear:
            con.execute(
              "UPDATE pc_conditions SET on_off=0 WHERE pc_id=? AND condition=?",
              (int(pc_id), c),
            )
            cleared.append(c)

    return {"ok": True, "pc_id": pc_id, "hp": int(row["max_hp"]), "cleared_conditions": cleared}

  @mcp.tool()
  def use_torch(pc_id: int, n: int = 1, item_name: str = "Torch") -> dict[str, Any]:
    """Consume torches (or another consumable) from inventory."""
    if n < 1:
      raise ValueError("n must be >= 1")

    with connect() as con:
      cur = con.execute(
        "SELECT qty FROM pc_items WHERE pc_id=? AND item=?",
        (int(pc_id), item_name),
      ).fetchone()

      have = int(cur["qty"]) if cur else 0
      new_qty = have - int(n)

      if new_qty <= 0:
        con.execute("DELETE FROM pc_items WHERE pc_id=? AND item=?", (int(pc_id), item_name))
        new_qty = 0
      else:
        con.execute(
          "INSERT INTO pc_items(pc_id,item,qty) VALUES (?,?,?) "
          "ON CONFLICT(pc_id,item) DO UPDATE SET qty=excluded.qty",
          (int(pc_id), item_name, new_qty),
        )

    return {"ok": True, "pc_id": pc_id, "item": item_name, "used": int(n), "qty": new_qty}

  @mcp.tool()
  def saving_throw(pc_id: int, save_type: str, mod: int = 0) -> dict[str, Any]:
    """
    Roll a saving throw vs a target stored in meta.saves[save_type].
    Pass if (d20 + mod) >= target.
    """
    import random

    save_type_key = save_type.strip().lower()

    with connect() as con:
      row = con.execute("SELECT meta_json FROM pcs WHERE id=?", (int(pc_id),)).fetchone()
      if not row:
        raise ValueError("pc_id not found")

      meta = json.loads(row["meta_json"] or "{}")
      saves = meta.get("saves", {})
      if save_type_key not in saves:
        raise ValueError(f"No save target for '{save_type_key}' in meta.saves")

      target = int(saves[save_type_key])

    roll = random.randint(1, 20)
    total = roll + int(mod)
    return {
      "pc_id": pc_id,
      "save_type": save_type_key,
      "roll": roll,
      "mod": int(mod),
      "total": total,
      "target": target,
      "pass": total >= target,
    }

  @mcp.tool()
  def attack_roll(
    pc_id: int,
    target_ac: int,
    mod: int = 0,
    ac_system: str = "descending",
  ) -> dict[str, Any]:
    """
    Attack roll using either:
    - descending AC with THAC0 (OSE-ish): need meta.thac0
    - ascending AC with attack bonus: need meta.attack_bonus
    """
    import random

    ac_system = ac_system.strip().lower()
    with connect() as con:
      row = con.execute("SELECT meta_json FROM pcs WHERE id=?", (int(pc_id),)).fetchone()
      if not row:
        raise ValueError("pc_id not found")

      meta = json.loads(row["meta_json"] or "{}")

    d20 = random.randint(1, 20)
    mod = int(mod)

    if ac_system == "descending":
      if "thac0" not in meta:
        raise ValueError("Missing meta.thac0 for descending AC attack rolls")
      thac0 = int(meta["thac0"])
      needed = thac0 - int(target_ac)
      total = d20 + mod
      hit = total >= needed
      return {
        "pc_id": pc_id,
        "ac_system": "descending",
        "d20": d20,
        "mod": mod,
        "total": total,
        "target_ac": int(target_ac),
        "thac0": thac0,
        "needed": needed,
        "hit": hit,
      }

    elif ac_system == "ascending":
      if "attack_bonus" not in meta:
        raise ValueError("Missing meta.attack_bonus for ascending AC attack rolls")
      atk = int(meta["attack_bonus"])
      total = d20 + atk + mod
      hit = total >= int(target_ac)
      return {
        "pc_id": pc_id,
        "ac_system": "ascending",
        "d20": d20,
        "attack_bonus": atk,
        "mod": mod,
        "total": total,
        "target_ac": int(target_ac),
        "hit": hit,
      }

    else:
      raise ValueError("ac_system must be 'descending' or 'ascending'")

  @mcp.tool()
  def set_thac0(pc_id: int, thac0: int) -> dict[str, Any]:
    """Set meta.thac0 for descending AC attack rolls."""
    with connect() as con:
      row = con.execute("SELECT meta_json FROM pcs WHERE id=?", (int(pc_id),)).fetchone()
      if not row:
        raise ValueError("pc_id not found")
      meta = json.loads(row["meta_json"] or "{}")
      meta["thac0"] = int(thac0)
      con.execute("UPDATE pcs SET meta_json=? WHERE id=?", (json.dumps(meta), int(pc_id)))
    return {"ok": True, "pc_id": pc_id, "thac0": int(thac0)}

  @mcp.tool()
  def set_saves(pc_id: int, saves: dict[str, int]) -> dict[str, Any]:
    """Set meta.saves dict, e.g. {'death':12,'wands':13,...}."""
    normalized = {k.strip().lower(): int(v) for k, v in (saves or {}).items()}
    with connect() as con:
      row = con.execute("SELECT meta_json FROM pcs WHERE id=?", (int(pc_id),)).fetchone()
      if not row:
        raise ValueError("pc_id not found")
      meta = json.loads(row["meta_json"] or "{}")
      meta["saves"] = normalized
      con.execute("UPDATE pcs SET meta_json=? WHERE id=?", (json.dumps(meta), int(pc_id)))
    return {"ok": True, "pc_id": pc_id, "saves": normalized}

  def _find_table_rows(text: str, required_words: list[str]) -> list[str]:
    """
    Heuristic: find a region containing required_words and return nearby lines.
    """
    lines = [ln.strip() for ln in (text or "").splitlines()]
    # find first line index that contains all required words (case-insensitive)
    req = [w.lower() for w in required_words]
    idx = None
    for i, ln in enumerate(lines):
      low = ln.lower()
      if all(w in low for w in req):
        idx = i
        break
    if idx is None:
      return []
    # return a window around it
    start = max(0, idx - 10)
    end = min(len(lines), idx + 120)
    return [ln for ln in lines[start:end] if ln]

  def _parse_thac0_from_lines(lines: list[str], level: int) -> int | None:
    import re
    level = int(level)

    for ln in lines:
      rng = _parse_level_range_prefix(ln)
      if not rng:
        continue
      lo, hi = rng
      if not (lo <= level <= hi):
        continue

      ints = [int(x) for x in re.findall(r"-?\d+", ln)]
      start = 2 if ("-" in ln.split()[0]) else 1

      if len(ints) >= start + 1:
        thac0 = ints[start]
        if 5 <= thac0 <= 25:
          return thac0

    return None

  def _parse_attack_bonus_from_lines(lines: list[str], level: int) -> int | None:
    import re
    level = int(level)

    for ln in lines:
      rng = _parse_level_range_prefix(ln)
      if not rng:
        continue
        lo, hi = rng
      if not (lo <= level <= hi):
        continue

      ints = [int(x) for x in re.findall(r"-?\d+", ln)]
      start = 2 if ("-" in ln.split()[0]) else 1

      if len(ints) >= start + 1:
        bonus = ints[start]
        if -5 <= bonus <= 20:
          return bonus

    return None

  def _parse_level_range_prefix(line: str) -> tuple[int, int] | None:
    """
    Parse a leading level or level-range token.
    Accepts:
      "5"   -> (5, 5)
      "1-3"   -> (1, 3)
      "10-12" -> (10, 12)
    """
    import re
    m = re.match(r"^\s*(\d+)\s*(?:-\s*(\d+))?", line)
    if not m:
      return None
    lo = int(m.group(1))
    hi = int(m.group(2)) if m.group(2) else lo
    if hi < lo:
      lo, hi = hi, lo
    return (lo, hi)

  def _parse_saves_from_lines(lines: list[str], level: int) -> dict[str, int] | None:
    """
    Parse saving throws from a line that starts with a level or level-range
    and contains 5 save values.
    Expected order: death, wands, paralysis, breath, spells.
    """
    import re
    level = int(level)

    for ln in lines:
      rng = _parse_level_range_prefix(ln)
      if not rng:
        continue
      lo, hi = rng
      if not (lo <= level <= hi):
        continue

      # Grab all ints. For a range row like "1-3 12 13 14 15 16"
      # ints will be [1, 3, 12, 13, 14, 15, 16]
      ints = [int(x) for x in re.findall(r"\d+", ln)]

      # Determine where the 5 saves start
      # If it’s a range, first two ints are lo, hi; else first int is level.
      start = 2 if ("-" in ln.split()[0]) else 1

      if len(ints) >= start + 5:
        death, wands, paralysis, breath, spells = ints[start:start+5]
        if all(2 <= v <= 20 for v in [death, wands, paralysis, breath, spells]):
          return {
            "death": death,
            "wands": wands,
            "paralysis": paralysis,
            "breath": breath,
            "spells": spells,
          }

    return None

  @mcp.tool()
  def populate_ose_tables(
    pc_id: int,
    klass: str,
    level: int,
    ac_system: str = "descending",
    apply: bool = True,
    max_refs: int = 5
  ) -> dict[str, Any]:
    """
    Populate PC meta with THAC0 / attack bonus and saving throws by parsing your local OSE SRD index.

    - ac_system: 'descending' (sets meta.thac0) or 'ascending' (sets meta.attack_bonus)
    - apply: if True, writes values into meta; if False, only returns what it found
    """
    klass = (klass or "").strip()
    if not klass:
      raise ValueError("klass is required")
    level = int(level)
    if level < 1:
      raise ValueError("level must be >= 1")

    ac_system = ac_system.strip().lower()
    if ac_system not in ("descending", "ascending"):
      raise ValueError("ac_system must be 'descending' or 'ascending'")

    # 1) Search refs for likely class pages / tables
    queries = [
      f"{klass} saving throws",
      f"{klass} thac0",
      f"{klass} attack",
      f"{klass} class",
    ]

    ref_hits: list[dict[str, Any]] = []
    with connect_refs() as con:
      for q in queries:
        rows = con.execute(
          """
          SELECT p.id, p.title, p.url,
               snippet(refs_fts, 1, '[', ']', '…', 16) AS snippet
          FROM refs_fts
          JOIN refs_pages p ON p.id = refs_fts.rowid
          WHERE refs_fts MATCH ?
          LIMIT ?
          """,
          (q, int(max_refs)),
        ).fetchall()
        for r in rows:
          d = dict(r)
          # de-dupe by id
          if not any(h["id"] == d["id"] for h in ref_hits):
            ref_hits.append(d)

    # 2) Try parsing from the top refs
    found_thac0 = None
    found_atk = None
    found_saves = None
    used_sources: list[dict[str, Any]] = []

    with connect_refs() as con:
      for hit in ref_hits[: int(max_refs)]:
        row = con.execute("SELECT id, title, url, text FROM refs_pages WHERE id=?", (int(hit["id"]),)).fetchone()
        if not row:
          continue
        title = row["title"] or ""
        url = row["url"] or ""
        text = row["text"] or ""

        # Pull candidate line windows
        th_lines = _find_table_rows(text, ["thac0"])
        atk_lines = _find_table_rows(text, ["attack"])
        sv_lines = _find_table_rows(text, ["saving", "throws"])

        # If we didn’t find keyword windows, fall back to whole text lines (short-circuit)
        if not th_lines:
          th_lines = [ln.strip() for ln in text.splitlines() if ln.strip()][:400]
        if not atk_lines:
          atk_lines = [ln.strip() for ln in text.splitlines() if ln.strip()][:400]
        if not sv_lines:
          sv_lines = [ln.strip() for ln in text.splitlines() if ln.strip()][:500]

        if ac_system == "descending" and found_thac0 is None:
          maybe = _parse_thac0_from_lines(th_lines, level)
          if maybe is not None:
            found_thac0 = maybe
            used_sources.append({"ref_id": int(row["id"]), "title": title, "url": url, "type": "thac0"})

        if ac_system == "ascending" and found_atk is None:
          maybe = _parse_attack_bonus_from_lines(atk_lines, level)
          if maybe is not None:
            found_atk = maybe
            used_sources.append({"ref_id": int(row["id"]), "title": title, "url": url, "type": "attack_bonus"})

        if found_saves is None:
          maybe = _parse_saves_from_lines(sv_lines, level)
          if maybe is not None:
            found_saves = maybe
            used_sources.append({"ref_id": int(row["id"]), "title": title, "url": url, "type": "saves"})

        # If we found everything we need, stop early
        if (ac_system == "descending" and found_thac0 is not None) or (ac_system == "ascending" and found_atk is not None):
          if found_saves is not None:
            break

    # 3) Apply to PC meta if requested
    applied = False
    if apply and ((ac_system == "descending" and found_thac0 is not None) or (ac_system == "ascending" and found_atk is not None) or (found_saves is not None)):
      with connect() as con:
        row = con.execute("SELECT meta_json, name, klass FROM pcs WHERE id=?", (int(pc_id),)).fetchone()
        if not row:
          raise ValueError("pc_id not found")

        meta = json.loads(row["meta_json"] or "{}")
        meta["klass"] = klass
        meta["level"] = level

        if ac_system == "descending" and found_thac0 is not None:
          meta["thac0"] = int(found_thac0)
        if ac_system == "ascending" and found_atk is not None:
          meta["attack_bonus"] = int(found_atk)
        if found_saves is not None:
          meta["saves"] = {k: int(v) for k, v in found_saves.items()}

        con.execute("UPDATE pcs SET meta_json=? WHERE id=?", (json.dumps(meta), int(pc_id)))
        applied = True

    # 4) Return results + fallbacks
    result = {
      "ok": True,
      "pc_id": int(pc_id),
      "klass": klass,
      "level": level,
      "ac_system": ac_system,
      "found": {
        "thac0": found_thac0,
        "attack_bonus": found_atk,
        "saves": found_saves,
      },
      "applied": applied,
      "sources_used": used_sources,
      "candidates": ref_hits[: int(max_refs)],
    }

    # Helpful hint if parsing failed
    if (ac_system == "descending" and found_thac0 is None) or (ac_system == "ascending" and found_atk is None) or (found_saves is None):
      result["hint"] = (
        "Auto-parse did not find everything. Use open_ref(ref_id) on a candidate to inspect the table, "
        "then set values manually with set_thac0()/set_saves() (or set attack_bonus). "
        "If you tell me which ref contains the class table, I can tighten the parser for that page format."
      )

    return result

