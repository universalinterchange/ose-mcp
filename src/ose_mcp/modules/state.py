from typing import Any
from ose_mcp.storage.db import connect

def register_state(mcp):
    @mcp.tool()
    def init_db() -> dict[str, Any]:
        """Initialize DB tables if missing."""
        with connect() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS pcs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              klass TEXT,
              hp INTEGER,
              max_hp INTEGER,
              json TEXT
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
    def create_pc(name: str, klass: str = "", hp: int = 1, max_hp: int = 1) -> dict[str, Any]:
        with connect() as con:
            cur = con.execute(
                "INSERT INTO pcs (name, klass, hp, max_hp, json) VALUES (?,?,?,?,?)",
                (name, klass, hp, max_hp, "{}"),
            )
            return {"pc_id": cur.lastrowid, "name": name, "klass": klass, "hp": hp, "max_hp": max_hp}

    @mcp.tool()
    def get_pc(pc_id: int) -> dict[str, Any]:
        with connect() as con:
            row = con.execute("SELECT * FROM pcs WHERE id=?", (pc_id,)).fetchone()
            if not row:
                raise ValueError("pc_id not found")
            return dict(row)

    @mcp.tool()
    def apply_damage(pc_id: int, amount: int) -> dict[str, Any]:
        with connect() as con:
            row = con.execute("SELECT hp, max_hp FROM pcs WHERE id=?", (pc_id,)).fetchone()
            if not row:
                raise ValueError("pc_id not found")
            new_hp = max(0, int(row["hp"]) - amount)
            con.execute("UPDATE pcs SET hp=? WHERE id=?", (new_hp, pc_id))
            return {"pc_id": pc_id, "damage": amount, "hp": new_hp, "max_hp": int(row["max_hp"])}

    @mcp.tool()
    def log_event(entry: str, tag: str = "") -> dict[str, Any]:
        with connect() as con:
            cur = con.execute("INSERT INTO log (tag, entry) VALUES (?,?)", (tag, entry))
            return {"log_id": cur.lastrowid, "tag": tag, "entry": entry}

    @mcp.tool()
    def recent_log(tag: str = "", limit: int = 10) -> dict[str, Any]:
        with connect() as con:
            if tag:
                rows = con.execute(
                    "SELECT * FROM log WHERE tag=? ORDER BY id DESC LIMIT ?",
                    (tag, limit),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM log ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return {"items": [dict(r) for r in rows]}

