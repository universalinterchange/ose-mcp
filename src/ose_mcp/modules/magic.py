import json
from typing import Any
from ose_mcp.storage.db import connect_campaign as connect

def init_mqgic() -> dict[str, Any]:
  with connect() as con:
    con.executescript("""
    CREATE TABLE IF NOT EXISTS spellbooks (
      pc_id INTEGER NOT NULL,
      spell TEXT NOT NULL,
      PRIMARY KEY (pc_id, spell)
    );
    CREATE TABLE IF NOT EXISTS prepared_spells (
      pc_id INTEGER NOT NULL,
      spell TEXT NOT NULL,
      qty INTEGER NOT NULL DEFAULT 1,
      PRIMARY KEY (pc_id, spell)
    );
    """)
  return {"ok": True}

def register_magic(mcp):
  @mcp.tool()
  def magic_init() -> dict:
    """Initialize spellbook and prepared-spell tables."""
    return init_magic()

  @mcp.tool()
  def set_spell_slots(pc_id: int, slots_by_level: dict[str, int]) -> dict[str, Any]:
    """
    Store exact spell slots in pc.meta.spell_slots, e.g. {"1":1,"2":0,"3":0}
    """
    with connect() as con:
      row = con.execute("SELECT meta_json FROM pcs WHERE id=?", (int(pc_id),)).fetchone()
      if not row:
        raise ValueError("pc_id not found")
      meta = json.loads(row["meta_json"] or "{}")
      meta["spell_slots"] = {str(k): int(v) for k, v in (slots_by_level or {}).items()}
      con.execute("UPDATE pcs SET meta_json=? WHERE id=?", (json.dumps(meta), int(pc_id)))
    return {"ok": True, "pc_id": int(pc_id), "spell_slots": meta["spell_slots"]}

  @mcp.tool()
  def learn_spell(pc_id: int, spell: str) -> dict[str, Any]:
    """Learn Spell by Name"""
    with connect() as con:
      con.execute("INSERT OR IGNORE INTO spellbooks(pc_id, spell) VALUES (?,?)", (int(pc_id), spell.strip()))
    return {"ok": True, "pc_id": int(pc_id), "spell": spell.strip()}

  @mcp.tool()
  def list_spells(pc_id: int) -> dict[str, Any]:
    """List Spells in Spellbook"""
    with connect() as con:
      known = con.execute("SELECT spell FROM spellbooks WHERE pc_id=? ORDER BY spell", (int(pc_id),)).fetchall()
      prep = con.execute("SELECT spell, qty FROM prepared_spells WHERE pc_id=? ORDER BY spell", (int(pc_id),)).fetchall()
    return {
      "pc_id": int(pc_id),
      "known": [r["spell"] for r in known],
      "prepared": [{"spell": r["spell"], "qty": int(r["qty"])} for r in prep],
    }

  @mcp.tool()
  def prepare_spell(pc_id: int, spell: str, qty: int = 1) -> dict[str, Any]:
    """Prepare Spells by Name"""
    q = max(1, int(qty))
    sp = spell.strip()
    with connect() as con:
      known = con.execute("SELECT 1 FROM spellbooks WHERE pc_id=? AND spell=?", (int(pc_id), sp)).fetchone()
      if not known:
        raise ValueError("spell not in spellbook; learn_spell first")
      con.execute(
        "INSERT INTO prepared_spells(pc_id, spell, qty) VALUES (?,?,?) "
        "ON CONFLICT(pc_id, spell) DO UPDATE SET qty=prepared_spells.qty + excluded.qty",
        (int(pc_id), sp, q),
      )
    return {"ok": True, "pc_id": int(pc_id), "spell": sp, "added": q}

  @mcp.tool()
  def cast_spell(pc_id: int, spell: str) -> dict[str, Any]:
    """Cast Spell by Name"""
    sp = spell.strip()
    with connect() as con:
      row = con.execute("SELECT qty FROM prepared_spells WHERE pc_id=? AND spell=?", (int(pc_id), sp)).fetchone()
      if not row or int(row["qty"]) <= 0:
        return {"ok": False, "error": "spell not prepared", "pc_id": int(pc_id), "spell": sp}
      qty = int(row["qty"]) - 1
      if qty <= 0:
        con.execute("DELETE FROM prepared_spells WHERE pc_id=? AND spell=?", (int(pc_id), sp))
      else:
        con.execute("UPDATE prepared_spells SET qty=? WHERE pc_id=? AND spell=?", (qty, int(pc_id), sp))
    return {"ok": True, "pc_id": int(pc_id), "spell": sp, "remaining_prepared": qty}
