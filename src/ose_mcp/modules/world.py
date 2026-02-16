import json
import random
from typing import Any
from ose_mcp.storage.db import connect_campaign as connect

def register_world(mcp):
  @mcp.tool()
  def world_init() -> dict[str, Any]:
    """Initialize world tables (NPCs, factions, relationships, rumors, sites, hexes, dungeons)."""
    with connect() as con:
      con.executescript("""
      PRAGMA foreign_keys=ON;

      CREATE TABLE IF NOT EXISTS npcs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        role TEXT,
        attitude INTEGER NOT NULL DEFAULT 0,
        meta_json TEXT NOT NULL DEFAULT '{}'
      );

      CREATE TABLE IF NOT EXISTS factions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        power INTEGER NOT NULL DEFAULT 1,
        meta_json TEXT NOT NULL DEFAULT '{}'
      );

      CREATE TABLE IF NOT EXISTS relationships (
        a_type TEXT NOT NULL, a_id INTEGER NOT NULL,
        b_type TEXT NOT NULL, b_id INTEGER NOT NULL,
        status TEXT NOT NULL, intensity INTEGER NOT NULL DEFAULT 1,
        meta_json TEXT NOT NULL DEFAULT '{}',
        PRIMARY KEY (a_type, a_id, b_type, b_id)
      );

      CREATE TABLE IF NOT EXISTS rumors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        truth INTEGER NOT NULL DEFAULT 1,
        used INTEGER NOT NULL DEFAULT 0,
        tags TEXT NOT NULL DEFAULT ''
      );

      CREATE TABLE IF NOT EXISTS sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        kind TEXT NOT NULL,
        hex_key TEXT,
        meta_json TEXT NOT NULL DEFAULT '{}'
      );

      CREATE TABLE IF NOT EXISTS hexes (
        hex_key TEXT PRIMARY KEY,
        discovered INTEGER NOT NULL DEFAULT 0,
        feature TEXT,
        meta_json TEXT NOT NULL DEFAULT '{}'
      );

      CREATE TABLE IF NOT EXISTS dungeons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        meta_json TEXT NOT NULL DEFAULT '{}'
      );

      CREATE TABLE IF NOT EXISTS dungeon_rooms (
        dungeon_id INTEGER NOT NULL,
        room_key TEXT NOT NULL,
        data_json TEXT NOT NULL,
        PRIMARY KEY (dungeon_id, room_key),
        FOREIGN KEY (dungeon_id) REFERENCES dungeons(id) ON DELETE CASCADE
      );

      CREATE TABLE IF NOT EXISTS dungeon_edges (
        dungeon_id INTEGER NOT NULL,
        a TEXT NOT NULL,
        b TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT 'door',
        meta_json TEXT NOT NULL DEFAULT '{}',
        PRIMARY KEY (dungeon_id, a, b),
        FOREIGN KEY (dungeon_id) REFERENCES dungeons(id) ON DELETE CASCADE
      );
      """)
    return {"ok": True}

  @mcp.tool()
  def create_npc(name: str | None = None, role: str | None = None, tags: list[str] | None = None) -> dict[str, Any]:
    tags = tags or []
    if not name:
      name = random.choice(["Aldo", "Brina", "Cora", "Dain", "Edda", "Fenn", "Garr", "Hale", "Ivo", "Jory"])
    meta = {"tags": tags}
    with connect() as con:
      cur = con.execute(
        "INSERT INTO npcs(name, role, meta_json) VALUES (?,?,?)",
        (name, role or "", json.dumps(meta)),
      )
    return {"npc_id": cur.lastrowid, "name": name, "role": role or "", "tags": tags}

  @mcp.tool()
  def npc_roster(query: str = "", limit: int = 25) -> dict[str, Any]:
    q = (query or "").strip().lower()
    with connect() as con:
      if q:
        rows = con.execute(
          "SELECT id, name, role, attitude FROM npcs WHERE lower(name) LIKE ? OR lower(role) LIKE ? LIMIT ?",
          (f"%{q}%", f"%{q}%", int(limit)),
        ).fetchall()
      else:
        rows = con.execute("SELECT id, name, role, attitude FROM npcs ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
    return {"npcs": [dict(r) for r in rows]}

  @mcp.tool()
  def create_faction(name: str, power: int = 1, tags: list[str] | None = None) -> dict[str, Any]:
    meta = {"tags": tags or []}
    with connect() as con:
      cur = con.execute(
        "INSERT INTO factions(name, power, meta_json) VALUES (?,?,?)",
        (name, int(power), json.dumps(meta)),
      )
    return {"faction_id": cur.lastrowid, "name": name, "power": int(power), "tags": meta["tags"]}

  @mcp.tool()
  def faction_list() -> dict[str, Any]:
    with connect() as con:
      rows = con.execute("SELECT id, name, power FROM factions ORDER BY id ASC").fetchall()
    return {"factions": [dict(r) for r in rows]}

  @mcp.tool()
  def relationship_set(a_type: str, a_id: int, b_type: str, b_id: int, status: str, intensity: int = 1) -> dict[str, Any]:
    st = (status or "neutral").strip().lower()
    with connect() as con:
      con.execute(
        "INSERT INTO relationships(a_type,a_id,b_type,b_id,status,intensity) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(a_type,a_id,b_type,b_id) DO UPDATE SET status=excluded.status, intensity=excluded.intensity",
        (a_type, int(a_id), b_type, int(b_id), st, int(intensity)),
      )
    return {"ok": True, "a": [a_type, int(a_id)], "b": [b_type, int(b_id)], "status": st, "intensity": int(intensity)}

  @mcp.tool()
  def record_rumor(text: str, truth: int = 1, tags: list[str] | None = None) -> dict[str, Any]:
    t = ",".join(tags or [])
    with connect() as con:
      cur = con.execute("INSERT INTO rumors(text, truth, tags) VALUES (?,?,?)", (text, int(truth), t))
    return {"rumor_id": cur.lastrowid, "text": text, "truth": int(truth), "tags": tags or []}

  @mcp.tool()
  def get_rumor(unused_only: bool = True) -> dict[str, Any]:
    with connect() as con:
      if unused_only:
        row = con.execute("SELECT * FROM rumors WHERE used=0 ORDER BY RANDOM() LIMIT 1").fetchone()
      else:
        row = con.execute("SELECT * FROM rumors ORDER BY RANDOM() LIMIT 1").fetchone()
      if not row:
        return {"ok": False, "error": "no rumors"}
      con.execute("UPDATE rumors SET used=1 WHERE id=?", (int(row["id"]),))
    return {"ok": True, "rumor": dict(row)}

  @mcp.tool()
  def hex_enter(hex_key: str) -> dict[str, Any]:
    """Enter a hex; if new, generate a feature and mark discovered."""
    hk = hex_key.strip().upper()
    with connect() as con:
      row = con.execute("SELECT * FROM hexes WHERE hex_key=?", (hk,)).fetchone()
      if row:
        d = dict(row)
        d["meta"] = json.loads(d["meta_json"] or "{}")
        return {"ok": True, "hex": d, "generated": False}

      feature = random.choice(["ruin", "lair", "hamlet", "odd landmark", "hazard", "resource", "nothing notable"])
      meta = {"notes": []}
      con.execute(
        "INSERT INTO hexes(hex_key, discovered, feature, meta_json) VALUES (?,?,?,?)",
        (hk, 1, feature, json.dumps(meta)),
      )
    return {"ok": True, "hex": {"hex_key": hk, "discovered": 1, "feature": feature, "meta": meta}, "generated": True}

  @mcp.tool()
  def create_dungeon(name: str) -> dict[str, Any]:
    with connect() as con:
      cur = con.execute("INSERT INTO dungeons(name) VALUES (?)", (name,))
    return {"dungeon_id": cur.lastrowid, "name": name}

  def _gen_room() -> dict[str, Any]:
    size = random.choice(["small chamber", "large chamber", "hallway", "odd shape", "huge area"])
    contents = random.choices(
      ["empty", "monster", "trap", "special", "treasure"],
      weights=[40, 30, 15, 10, 5],
      k=1
    )[0]
    exits = random.choice(["1 exit", "2 exits", "3 exits", "4+ exits"])
    detail = random.choice(["damp stone", "dusty floor", "fresh drafts", "sulfur smell", "cobwebs", "scuff marks"])
    return {"size": size, "contents": contents, "exits": exits, "detail": detail}

  @mcp.tool()
  def enter_room(dungeon_id: int, room_key: str) -> dict[str, Any]:
    """Return persistent room data; generate if missing."""
    rk = room_key.strip().upper()
    with connect() as con:
      row = con.execute(
        "SELECT data_json FROM dungeon_rooms WHERE dungeon_id=? AND room_key=?",
        (int(dungeon_id), rk),
      ).fetchone()
      if row:
        return {"ok": True, "dungeon_id": int(dungeon_id), "room_key": rk, "room": json.loads(row["data_json"]), "generated": False}

      room = _gen_room()
      con.execute(
        "INSERT INTO dungeon_rooms(dungeon_id, room_key, data_json) VALUES (?,?,?)",
        (int(dungeon_id), rk, json.dumps(room)),
      )
    return {"ok": True, "dungeon_id": int(dungeon_id), "room_key": rk, "room": room, "generated": True}

  @mcp.tool()
  def connect_rooms(dungeon_id: int, a: str, b: str, kind: str = "door") -> dict[str, Any]:
    """Persist a connection between rooms."""
    a = a.strip().upper()
    b = b.strip().upper()
    k = (kind or "door").strip().lower()
    with connect() as con:
      con.execute(
        "INSERT OR IGNORE INTO dungeon_edges(dungeon_id,a,b,kind) VALUES (?,?,?,?)",
        (int(dungeon_id), a, b, k),
      )
      con.execute(
        "INSERT OR IGNORE INTO dungeon_edges(dungeon_id,a,b,kind) VALUES (?,?,?,?)",
        (int(dungeon_id), b, a, k),
      )
    return {"ok": True, "dungeon_id": int(dungeon_id), "a": a, "b": b, "kind": k}

  @mcp.tool()
  def faction_turn(weeks: int = 1) -> dict[str, Any]:
    """
    Advance the world by weeks:
    - randomly selects factions to act
    - creates simple events
    - logs them (uses existing log table from state module)
    """
    w = max(1, int(weeks))
    events: list[dict[str, Any]] = []
    with connect() as con:
      facs = con.execute("SELECT id, name, power FROM factions").fetchall()
      if not facs:
        return {"ok": True, "weeks": w, "events": [], "note": "no factions"}

      for _ in range(w):
        # 1-3 events per week
        for __ in range(random.randint(1, 3)):
          f = dict(random.choice(facs))
          action = random.choice(["presses claims", "recruits", "spreads rumors", "raids", "negotiates", "moves covertly"])
          target = random.choice(["a rival", "the locals", "a site", "a caravan", "the authorities", "an ally"])
          evt = {"faction": f["name"], "power": f["power"], "event": f"{f['name']} {action} against {target}."}
          events.append(evt)

      # write to log if it exists
      con.executescript("""
      CREATE TABLE IF NOT EXISTS log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT DEFAULT (datetime('now')),
        tag TEXT,
        entry TEXT NOT NULL
      );
      """)
      for e in events:
        con.execute("INSERT INTO log(tag, entry) VALUES (?,?)", ("faction_turn", e["event"]))

    return {"ok": True, "weeks": w, "events": events}

  @mcp.tool()
  def region_seed(
    region: str,
    center_hex: str = "A1",
    radius: int = 2,
    biome: str = "plains",
    danger_level: int = 1
  ) -> dict[str, Any]:
    """
    Pre-create hex records in a loose 'radius' around a named region.
    We don't enforce real hex geometry here; we just create keys like A1.. for convenience.
    If you want real axial coords later, we can swap representation.
    """
    reg = region.strip()
    bio = (biome or "plains").lower()
    rad = max(0, int(radius))
    created = 0

    # Simple key scheme: letter+number like A1, A2... seed a block
    col = center_hex.strip().upper()[0]
    try:
      row0 = int(center_hex.strip().upper()[1:])
    except Exception:
      row0 = 1

    cols = [chr(ord(col) + dc) for dc in range(-rad, rad + 1)]
    rows = [row0 + dr for dr in range(-rad, rad + 1)]

    with connect() as con:
      for c in cols:
        for r in rows:
          hk = f"{c}{r}"
          exists = con.execute("SELECT 1 FROM hexes WHERE hex_key=?", (hk,)).fetchone()
          if exists:
              continue
          meta = {"region": reg, "biome": bio, "danger_level": int(danger_level), "notes": []}
          con.execute(
              "INSERT INTO hexes(hex_key, discovered, feature, meta_json) VALUES (?,?,?,?)",
              (hk, 0, None, json.dumps(meta)),
          )
          created += 1

    return {"ok": True, "region": reg, "center_hex": center_hex, "radius": rad, "created": created, "biome": bio, "danger_level": int(danger_level)}

  @mcp.tool()
  def hex_discover(hex_key: str) -> dict[str, Any]:
    """
    Like hex_enter, but guarantees generation and flips discovered=1.
    """
    hk = hex_key.strip().upper()
    with connect() as con:
      row = con.execute("SELECT * FROM hexes WHERE hex_key=?", (hk,)).fetchone()
      if not row:
        meta = {"region": "", "biome": "plains", "danger_level": 1, "notes": []}
        feature = random.choice(["ruin", "lair", "hamlet", "odd landmark", "hazard", "resource", "nothing notable"])
        con.execute(
          "INSERT INTO hexes(hex_key, discovered, feature, meta_json) VALUES (?,?,?,?)",
          (hk, 1, feature, json.dumps(meta)),
        )
        return {"ok": True, "hex": {"hex_key": hk, "discovered": 1, "feature": feature, "meta": meta}, "generated": True}

      d = dict(row)
      meta = json.loads(d.get("meta_json") or "{}")
      if not d.get("feature"):
        d["feature"] = random.choice(["ruin", "lair", "hamlet", "odd landmark", "hazard", "resource", "nothing notable"])
      con.execute("UPDATE hexes SET discovered=1, feature=?, meta_json=? WHERE hex_key=?", (d["feature"], json.dumps(meta), hk))
      d["meta"] = meta
      return {"ok": True, "hex": d, "generated": False}

  @mcp.tool()
  def site_create(name: str, kind: str, hex_key: str | None = None, tags: list[str] | None = None) -> dict[str, Any]:
    meta = {"tags": tags or []}
    with connect() as con:
      cur = con.execute(
        "INSERT INTO sites(name, kind, hex_key, meta_json) VALUES (?,?,?,?)",
        (name, kind, (hex_key.strip().upper() if hex_key else None), json.dumps(meta)),
      )
    return {"ok": True, "site_id": cur.lastrowid, "name": name, "kind": kind, "hex_key": hex_key, "tags": meta["tags"]}

  @mcp.tool()
  def site_list(hex_key: str | None = None) -> dict[str, Any]:
    with connect() as con:
      if hex_key:
        hk = hex_key.strip().upper()
        rows = con.execute("SELECT id, name, kind, hex_key FROM sites WHERE hex_key=? ORDER BY id", (hk,)).fetchall()
      else:
        rows = con.execute("SELECT id, name, kind, hex_key FROM sites ORDER BY id DESC LIMIT 50").fetchall()
    return {"sites": [dict(r) for r in rows]}

  @mcp.tool()
  def town_generate(name: str, hex_key: str, size: str = "village") -> dict[str, Any]:
    """
    Create a persistent town site plus a starter set of NPCs and services.
    """
    hk = hex_key.strip().upper()
    sz = (size or "village").lower()

    # Basic services by size
    services = {
      "hamlet": ["inn (rough)", "general goods (limited)"],
      "village": ["inn", "general goods", "temple/shrine", "blacksmith"],
      "town": ["inn", "market", "temple", "blacksmith", "sage", "stable"],
      "city": ["multiple inns", "guilds", "temples", "specialists", "magic broker"],
    }
    svc = services.get(sz, services["village"])

    # Create site + a few NPCs
    site = site_create(name, "town", hk, tags=[sz])

    npc_ids = []
    npc_ids.append(create_npc(role="innkeeper", tags=["town", name])["npc_id"])
    npc_ids.append(create_npc(role="guard captain", tags=["town", name])["npc_id"])
    npc_ids.append(create_npc(role="priest", tags=["town", name])["npc_id"])
    if sz in ("town", "city"):
      npc_ids.append(create_npc(role="guild rep", tags=["town", name])["npc_id"])

    # Seed a couple rumors
    record_rumor(f"Someone in {name} is paying for information about a nearby ruin.", truth=1, tags=["town", name])
    record_rumor(f"A traveler swears a beast haunts the road near {hk}.", truth=1, tags=["town", name])

    # Store services on the site meta
    with connect() as con:
      row = con.execute("SELECT meta_json FROM sites WHERE id=?", (int(site["site_id"]),)).fetchone()
      meta = json.loads(row["meta_json"] or "{}")
      meta["services"] = svc
      meta["npc_ids"] = npc_ids
      con.execute("UPDATE sites SET meta_json=? WHERE id=?", (json.dumps(meta), int(site["site_id"])))

    return {"ok": True, "site": site, "services": svc, "npc_ids": npc_ids}
