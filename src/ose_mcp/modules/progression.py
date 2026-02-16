import json
import random
from typing import Any
from ose_mcp.storage.db import connect_campaign as connect

def _load_pc(con, pc_id: int) -> dict[str, Any]:
  row = con.execute("SELECT id,name,klass,hp,max_hp,meta_json FROM pcs WHERE id=?", (int(pc_id),)).fetchone()
  if not row:
    raise ValueError("pc_id not found")
  d = dict(row)
  d["meta"] = json.loads(d.pop("meta_json") or "{}")
  return d

def _save_meta(con, pc_id: int, meta: dict[str, Any]) -> None:
  con.execute("UPDATE pcs SET meta_json=? WHERE id=?", (json.dumps(meta), int(pc_id)))

def _xp_thresholds_for(meta: dict[str, Any]) -> list[int]:
  # thresholds like [0, 2000, 4000, 8000, ...] for levels 1..N
  t = meta.get("xp_thresholds")
  if isinstance(t, list) and all(isinstance(x, (int, float)) for x in t) and len(t) >= 2:
    return [int(x) for x in t]
  # safe fallback (NOT OSE-accurate): flat doubling
  base = int(meta.get("xp_base", 2000))
  out = [0]
  v = base
  for _ in range(1, 15):
    out.append(v)
    v *= 2
  return out

def _calc_level(xp: int, thresholds: list[int]) -> int:
  lvl = 1
  for i, req in enumerate(thresholds[1:], start=2):
    if xp >= req:
      lvl = i
    else:
      break
  return lvl

def register_progression(mcp):
  @mcp.tool()
  def progression_init() -> dict[str, Any]:
    """No schema needed; uses pcs.meta_json."""
    return {"ok": True}

  @mcp.tool()
  def set_xp_table(pc_id: int, thresholds: list[int]) -> dict[str, Any]:
    """
    Set exact XP thresholds for levels.
    Example: [0, 2000, 4000, 8000, 16000, ...] where index = level.
    """
    if not thresholds or thresholds[0] != 0:
      raise ValueError("thresholds must start with 0 for level 1")
    with connect() as con:
      pc = _load_pc(con, pc_id)
      meta = pc["meta"]
      meta["xp_thresholds"] = [int(x) for x in thresholds]
      meta.setdefault("xp", 0)
      meta.setdefault("level", 1)
      _save_meta(con, pc_id, meta)
    return {"ok": True, "pc_id": int(pc_id), "xp_thresholds": meta["xp_thresholds"]}

  @mcp.tool()
  def set_hit_dice(pc_id: int, hd: str) -> dict[str, Any]:
    """
    Store class HD expression, e.g. 'd8' or 'd6'. Used for level-up HP roll.
    """
    h = (hd or "").strip().lower()
    if not h.startswith("d"):
      raise ValueError("hd must look like 'd8'")
    sides = int(h[1:])
    if sides not in (4, 6, 8, 10, 12):
      raise ValueError("unusual HD sides; expected d4/d6/d8/d10/d12")
    with connect() as con:
      pc = _load_pc(con, pc_id)
      meta = pc["meta"]
      meta["hd"] = h
      _save_meta(con, pc_id, meta)
    return {"ok": True, "pc_id": int(pc_id), "hd": h}

  @mcp.tool()
  def check_level_up(pc_id: int) -> dict[str, Any]:
    """Return current xp, level, and whether next level is available."""
    with connect() as con:
      pc = _load_pc(con, pc_id)
      meta = pc["meta"]
      xp = int(meta.get("xp", 0))
      thresholds = _xp_thresholds_for(meta)
      cur_level = int(meta.get("level", 1))
      calc_level = _calc_level(xp, thresholds)
      next_req = thresholds[cur_level] if cur_level < len(thresholds) else None
      return {
        "pc_id": int(pc_id),
        "name": pc["name"],
        "klass": pc["klass"],
        "xp": xp,
        "level": cur_level,
        "calc_level": calc_level,
        "can_level": calc_level > cur_level,
        "next_level_xp": next_req,
        "thresholds_len": len(thresholds),
      }

  @mcp.tool()
  def level_up(pc_id: int, levels: int = 1, hp_method: str = "roll", hp_min_gain: int = 1) -> dict[str, Any]:
    """
    Apply level-up(s):
    - increments meta.level
    - increases max_hp by HD roll (or average)
    - sets hp to max_hp (classic OSR between delves; adjust if you dislike)
    """
    lvls = max(1, int(levels))
    method = (hp_method or "roll").lower()

    with connect() as con:
      pc = _load_pc(con, pc_id)
      meta = pc["meta"]
      meta.setdefault("xp", 0)
      meta.setdefault("level", 1)
      hd = meta.get("hd", "d8")
      sides = int(str(hd).lower().replace("d", "") or 8)

      old_level = int(meta["level"])
      new_level = old_level
      gains = []

      for _ in range(lvls):
        new_level += 1
        if method == "avg":
          gain = max(int(hp_min_gain), (sides + 1) // 2)
        else:
          gain = max(int(hp_min_gain), random.randint(1, sides))
        gains.append(gain)

      meta["level"] = new_level

      # update hp/max_hp on pcs table
      new_max = int(pc["max_hp"]) + sum(gains)
      con.execute("UPDATE pcs SET max_hp=?, hp=? WHERE id=?", (new_max, new_max, int(pc_id)))

      _save_meta(con, pc_id, meta)

    return {"ok": True, "pc_id": int(pc_id), "old_level": old_level, "new_level": new_level, "hp_gains": gains, "new_max_hp": new_max}

  @mcp.tool()
  def award_xp(pc_id: int, amount: int) -> dict[str, Any]:
    """Add XP to pc.meta.xp."""
    with connect() as con:
      pc = _load_pc(con, pc_id)
      meta = pc["meta"]
      meta["xp"] = int(meta.get("xp", 0)) + int(amount)
      _save_meta(con, pc_id, meta)
    return {"ok": True, "pc_id": int(pc_id), "awarded": int(amount), "xp": meta["xp"]}

