import os
import sqlite3
from typing import Any
import importlib.metadata

from ose_mcp.storage.db import connect_campaign as connect_campaign

try:
  from ose_mcp.storage.db import connect_refs as connect_refs  # optional
except Exception:
  connect_refs = None


SCHEMA_VERSION = 1

# Tables you almost certainly want in campaign.sqlite for your system
REQUIRED_CAMPAIGN_TABLES = [
  "pcs",
  "pc_items",
  "pc_conditions",
  "npcs",
  "factions",
  "relationships",
  "hexes",
  "sites",
  "dungeons",
  "dungeon_rooms",
  "dungeon_edges",
  "proc_state",
  "time_state",
  "oracle_state",
  "encounter_tables",
  "encounter_entries",
  "log",
]

# Tables expected in refs.sqlite (your SRD index)
REQUIRED_REFS_TABLES = [
  "refs_pages",
  "refs_fts",
]


def _db_path(con: sqlite3.Connection) -> str | None:
  try:
    row = con.execute("PRAGMA database_list;").fetchone()
    # columns: seq, name, file
    if row and row[2]:
      return str(row[2])
  except Exception:
    pass
  return None


def _list_tables(con: sqlite3.Connection) -> list[str]:
  rows = con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
  ).fetchall()
  return [r[0] for r in rows]


def _integrity_check(con: sqlite3.Connection) -> dict[str, Any]:
  # integrity_check can be expensive, but your DBs are small
  try:
    rows = con.execute("PRAGMA integrity_check;").fetchall()
    msgs = [r[0] for r in rows]
    ok = (len(msgs) == 1 and msgs[0].lower() == "ok")
    return {"ok": ok, "messages": msgs[:50]}
  except Exception as e:
    return {"ok": False, "error": str(e)}


def _ensure_schema_meta(con: sqlite3.Connection) -> None:
  con.executescript("""
  CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
  );
  """)
  con.execute(
    "INSERT OR IGNORE INTO schema_meta(key, value) VALUES ('schema_version', ?)",
    (str(SCHEMA_VERSION),)
  )


def _get_schema_version(con: sqlite3.Connection) -> int | None:
  try:
    _ensure_schema_meta(con)
    row = con.execute(
      "SELECT value FROM schema_meta WHERE key='schema_version'"
    ).fetchone()
    if not row:
      return None
    return int(row[0])
  except Exception:
    return None


def _count_safe(con: sqlite3.Connection, table: str) -> int | None:
  try:
    row = con.execute(f"SELECT COUNT(*) FROM {table};").fetchone()
    return int(row[0]) if row else 0
  except Exception:
    return None


def _fts_ok(con: sqlite3.Connection, fts_table: str) -> dict[str, Any]:
  # Basic sanity: table exists + can query
  try:
    con.execute(f"SELECT rowid FROM {fts_table} LIMIT 1;").fetchone()
    return {"ok": True}
  except Exception as e:
    return {"ok": False, "error": str(e)}


def _pkg_version() -> str | None:
  # your dist name may be "ose-mcp" or "ose_mcp" depending on pyproject
  for name in ("ose-mcp", "ose_mcp"):
    try:
      return importlib.metadata.version(name)
    except Exception:
      continue
  return None


def register_ops(mcp):

  @mcp.tool()
  def version() -> dict[str, Any]:
    """
    Return ose-mcp package version plus schema version (stored in campaign.sqlite).
    """
    pkg = _pkg_version()

    with connect_campaign() as con:
      schema_v = _get_schema_version(con)
      db = _db_path(con)

    return {
      "ok": True,
      "package_version": pkg,
      "schema_version": schema_v,
      "schema_version_current": SCHEMA_VERSION,
      "campaign_db": db,
    }

  @mcp.tool()
  def doctor(check_integrity: bool = True) -> dict[str, Any]:
    """
    Sanity checks:
    - campaign DB path + required tables
    - optional refs DB path + required tables + index counts
    - optional PRAGMA integrity_check
    """
    report: dict[str, Any] = {"ok": True, "campaign": {}, "refs": {}}

    # --- campaign checks ---
    with connect_campaign() as con:
      campaign_path = _db_path(con)
      tables = _list_tables(con)
      schema_v = _get_schema_version(con)

      missing = [t for t in REQUIRED_CAMPAIGN_TABLES if t not in tables]

      report["campaign"] = {
        "db_path": campaign_path,
        "db_exists": bool(campaign_path and os.path.exists(campaign_path)),
        "schema_version": schema_v,
        "tables_count": len(tables),
        "missing_required_tables": missing,
      }

      if check_integrity:
        report["campaign"]["integrity_check"] = _integrity_check(con)

    # mark overall ok
    if report["campaign"]["missing_required_tables"]:
      report["ok"] = False
    if check_integrity and not report["campaign"].get("integrity_check", {}).get("ok", True):
      report["ok"] = False

    # --- refs checks (optional) ---
    if connect_refs is None:
      report["refs"] = {
        "available": False,
        "reason": "connect_refs not available in ose_mcp.storage.db"
      }
      return report

    try:
      with connect_refs() as conr:
        refs_path = _db_path(conr)
        rtables = _list_tables(conr)
        rmissing = [t for t in REQUIRED_REFS_TABLES if t not in rtables]

        pages = _count_safe(conr, "refs_pages")
        # refs_fts is an FTS virtual table; COUNT(*) works if it’s healthy
        fts_rows = _count_safe(conr, "refs_fts")

        fts_health = _fts_ok(conr, "refs_fts")

        report["refs"] = {
          "available": True,
          "db_path": refs_path,
          "db_exists": bool(refs_path and os.path.exists(refs_path)),
          "tables_count": len(rtables),
          "missing_required_tables": rmissing,
          "refs_pages_count": pages,
          "refs_fts_rows": fts_rows,
          "refs_fts_ok": fts_health,
        }

        if check_integrity:
          report["refs"]["integrity_check"] = _integrity_check(conr)

      if report["refs"]["missing_required_tables"]:
        report["ok"] = False
      if not report["refs"]["refs_fts_ok"].get("ok", True):
        report["ok"] = False
      if check_integrity and not report["refs"].get("integrity_check", {}).get("ok", True):
        report["ok"] = False

    except Exception as e:
      report["refs"] = {"available": False, "error": str(e)}

    return report

  @mcp.tool()
  def lint_tools(strict: bool = False, limit: int | None = None, review_docstrings:bool = False, suggest_docstrings: bool = False, min_doc_len: int = 30,) -> dict[str, Any]:
    """
    Lint registered MCP tools:
    - duplicate tool name registrations
    - missing docstrings (with suggested one-liners)
    - unhelpful docstrings (too short/generic/redundant), with improved suggestions

    strict: if True, ok=False when any errors found
    limit: optional cap on returned list sizes (None = no cap)
    suggest_docstrings: include suggested docstrings/stub lines
    review_existing_docstrings: analyze existing docstrings for usefulness
    min_doc_len: minimum “helpful” length threshold (heuristic)
    """
    regs = getattr(mcp, "_ose_tool_registrations", None)
    meta = getattr(mcp, "_ose_tool_meta", None)

    if not isinstance(regs, list) or not isinstance(meta, dict):
      return {
        "ok": False,
        "error": "help registry not available. Ensure register_help(mcp) is called before other register_* calls.",
      }

    def cap(xs):
      if limit is None:
        return xs
      try:
        lim = int(limit)
      except Exception:
        return xs
      lim = max(0, lim)
      return xs[:lim]

    def _words(name: str) -> list[str]:
      return [w for w in (name or "").strip().split("_") if w]

    def _normalize(s: str) -> str:
      return " ".join((s or "").strip().lower().split())

    def _generic_doc(d: str) -> bool:
      dd = _normalize(d)
      generics = {
        "tool.",
        "tool",
        "initialize.",
        "initialize",
        "init.",
        "init",
        "get.",
        "get",
        "set.",
        "set",
        "list.",
        "list",
        "create.",
        "create",
        "delete.",
        "delete",
        "update.",
        "update",
        "run.",
        "run",
      }
      if dd in generics:
        return True
      # Also catch “Initialize X.” where X is 1 token
      if dd.startswith("initialize ") and len(dd.split()) <= 3:
        return True
      if dd.startswith("set ") and len(dd.split()) <= 3:
        return True
      if dd.startswith("get ") and len(dd.split()) <= 3:
        return True
      if dd.startswith("list ") and len(dd.split()) <= 3:
        return True
      if dd.startswith("create ") and len(dd.split()) <= 3:
        return True
      return False

    def _doc_mentions_return(d: str) -> bool:
      dd = _normalize(d)
      return any(k in dd for k in ["return", "returns", "result", "dict", "id", "ids", "record", "details", "updated"])

    def _doc_mentions_side_effect(d: str) -> bool:
      dd = _normalize(d)
      return any(k in dd for k in ["save", "persist", "store", "update", "write", "database", "db", "insert", "delete"])

    def _doc_mentions_example(d: str) -> bool:
      return "(" in (d or "") and ")" in (d or "") and "e.g." in (d or "").lower()

    def _suggest_doc(name: str, mod: str, sig: str) -> str:
      # Human-ish one-liners tailored to common RPG actions
      verb = (_words(name)[:1] or ["do"])[0]
      rest = " ".join(_words(name)[1:])

      specials = {
        "roll": "Roll dice using NdM(+/-K) notation and return total and rolls.",
        "reaction_roll": "Roll a 2d6 reaction check and return the band/result.",
        "morale_check": "Roll a 2d6 morale check and return pass/fail.",
        "encounter_check": "Roll a wandering encounter check and return whether it triggers.",
        "surprise_check": "Roll surprise check and return who is surprised.",
        "distance_check": "Generate encounter distance and return result.",
        "apply_damage": "Apply damage to a PC and return updated HP.",
        "heal": "Heal a PC and return updated HP.",
        "add_item": "Add an item to PC inventory (increments qty if already present).",
        "use_torch": "Consume a torch and/or update light state.",
        "consume_rations": "Consume rations from inventory.",
        "set_condition": "Set or clear a condition on a PC.",
        "long_rest": "Apply a long rest (clear rest-based conditions, optionally heal).",
        "buy_item": "Buy an item: subtract coins and add it to PC inventory.",
        "sell_item": "Sell an item: remove from inventory and add coins.",
        "learn_spell": "Add a spell to a PC spellbook.",
        "prepare_spell": "Prepare a spell from spellbook for casting.",
        "cast_spell": "Cast a prepared spell and decrement prepared uses.",
        "list_spells": "List a PC’s known and prepared spells.",
        "recruit_hireling": "Recruit a hireling and return the hireling record.",
        "hireling_roster": "List hirelings, optionally filtered by status.",
        "pay_wages": "Pay wages for active hirelings and return total cost.",
        "reputation_get": "Return current reputation.",
        "reputation_adjust": "Adjust reputation by delta and return updated value.",
        "quest_generate": "Generate a quest hook and persist it to the campaign.",
        "quest_list": "List quests, optionally filtered by status.",
        "quest_set_status": "Set quest status (open/completed/failed).",
        "search_refs": "Search the OSE SRD index and return best-matching pages.",
        "open_ref": "Open an SRD reference and return the content/summary.",
        "gm_step": "Run one GM-less step and return next prompts/actions.",
      }
      if name in specials:
        return specials[name]

      if name.endswith("_init") or verb == "init":
        target = rest if rest else (mod or "system")
        return f"Initialize {target} tables/state (safe to run multiple times)."

      if verb == "create":
        target = rest or "record"
        return f"Create {target} and return its id/record."
      if verb == "get":
        target = rest or "record"
        return f"Get {target}."
      if verb == "list":
        target = rest or "records"
        return f"List {target}."
      if verb == "set":
        target = rest or "value"
        return f"Set {target}."
      if verb == "delete":
        target = rest or "record"
        return f"Delete {target}."
      if verb == "rename":
        target = rest or "record"
        return f"Rename {target}."

      if mod:
        return f"{mod}: {verb} {rest or name}."
      return f"{verb.capitalize()} {rest or name}."

    def _doc_quality(name: str, desc: str) -> dict[str, Any]:
      # Heuristic scoring: 0..100
      d = (desc or "").strip()
      dd = _normalize(d)
      name_n = _normalize(name.replace("_", " "))

      score = 100
      reasons = []

      if not d:
        return {"score": 0, "reasons": ["missing"]}

      if _generic_doc(d):
        score -= 50
        reasons.append("generic")

      if len(d) < int(min_doc_len):
        score -= 20
        reasons.append("too_short")

      # Redundant if docstring mostly repeats function name words
      overlap = 0
      for w in name_n.split():
        if w and w in dd:
          overlap += 1
      if overlap >= max(2, len(name_n.split()) // 2) and len(dd.split()) <= len(name_n.split()) + 3:
        score -= 25
        reasons.append("redundant_with_name")

      if not _doc_mentions_return(d):
        score -= 10
        reasons.append("no_return_hint")

      # Side-effect hint is nice for DB-writing tools, but we can't always know.
      # We only lightly penalize.
      if not _doc_mentions_side_effect(d):
        score -= 5
        reasons.append("no_side_effect_hint")

      score = max(0, min(100, score))
      return {"score": score, "reasons": reasons}

    # duplicates
    counts: dict[str, int] = {}
    for n in regs:
      counts[n] = counts.get(n, 0) + 1
    duplicates = sorted([n for n, c in counts.items() if c > 1])

    # missing docstrings + suggestions
    missing = []
    for n, info in meta.items():
      desc = (info.get("description") or "").strip()
      if desc:
        continue
      mod = (info.get("module") or "").strip()
      sig = (info.get("signature") or "").strip()
      item = {"tool": n, "module": mod, "signature": sig}
      if suggest_docstrings or review_docstrings:
        item["suggested"] = _suggest_doc(n, mod, sig)
        item["stub_line"] = f'  """{item["suggested"]}"""'
      missing.append(item)
    missing.sort(key=lambda x: x["tool"])

    # review existing docstrings (boring/unhelpful)
    unhelpful = []
    if review_docstrings:
      for n, info in meta.items():
        desc = (info.get("description") or "").strip()
        if not desc:
          continue
        mod = (info.get("module") or "").strip()
        sig = (info.get("signature") or "").strip()
        q = _doc_quality(n, desc)

        # Flag if low score OR specific bad patterns
        if q["score"] < 70 or "generic" in q["reasons"] or "redundant_with_name" in q["reasons"]:
          item = {
            "tool": n,
            "module": mod,
            "signature": sig,
            "current": desc,
            "score": q["score"],
            "reasons": q["reasons"],
          }
          if suggest_docstrings or review_docstrings:
            item["suggested"] = _suggest_doc(n, mod, sig)
            item["stub_line"] = f'  """{item["suggested"]}"""'
          unhelpful.append(item)

      unhelpful.sort(key=lambda x: (x["score"], x["tool"]))

    errors = []
    if duplicates:
      errors.append("duplicate_tool_names")

    ok = True
    if strict and errors:
      ok = False

    return {
      "ok": ok,
      "errors": errors,
      "counts": {
        "registered_calls": len(regs),
        "unique_tools": len(set(regs)),
        "duplicates": len(duplicates),
        "doc_missing": len(missing),
        "doc_unhelpful": len(unhelpful),
      },
      "duplicates": cap([{"tool": n, "count": counts[n]} for n in duplicates]),
      "missing_docstrings": cap(missing),
      "unhelpful_docstrings": cap(unhelpful),
    }

  @mcp.tool()
  def docstring_stub(tool: str | None = None, wrap: int = 88) -> dict[str, Any]:
    """
    Generate ready-to-paste one-line docstring stubs.

    tool:
      - if provided: generate stub for that tool (or suggestions if not found)
      - if omitted: generate stubs for all tools missing docstrings

    wrap:
      - max line width for docstring content
    """
    regs = getattr(mcp, "_ose_tool_registrations", None)
    meta = getattr(mcp, "_ose_tool_meta", None)

    if not isinstance(regs, list) or not isinstance(meta, dict):
      return {
        "ok": False,
        "error": "help registry not available. Ensure register_help(mcp) is called before other register_* calls.",
      }

    def _wrap_one_line(s: str, width: int) -> str:
      # Keep it one line; if too long, truncate cleanly.
      w = max(40, int(width))
      if len(s) <= w:
        return s
      return s[: max(0, w - 3)].rstrip() + "..."

    # Find tools missing docstrings
    missing = []
    for name, info in meta.items():
      desc = (info.get("description") or "").strip()
      if not desc:
        missing.append(name)
    missing.sort()

    # If tool specified, narrow to one
    if tool is not None:
      q = tool.strip()
      if q in meta:
        target = [q] if q in missing else []
      else:
        # Suggest close matches
        keys = sorted(meta.keys())
        sugg = [k for k in keys if q.lower() in k.lower()]
        return {"ok": False, "error": "tool not found", "query": tool, "suggestions": sugg[:50]}

      if not target:
        return {"ok": True, "message": "Tool already has a docstring (or tool has no metadata).", "tool": q}

      name = target[0]
      info = meta.get(name, {})
      mod = (info.get("module") or "module").strip()
      sig = (info.get("signature") or "").strip()

      # Default stub text: use module + tool name
      base = f"{mod}: {name}{sig}".strip()
      text = _wrap_one_line(f"{base}.", wrap)

      stub = f'  """{text}"""'
      return {
        "ok": True,
        "tool": name,
        "module": mod,
        "signature": sig,
        "stub_line": stub,
      }

    # Otherwise generate for all missing
    stubs = []
    for name in missing:
      info = meta.get(name, {})
      mod = (info.get("module") or "module").strip()
      sig = (info.get("signature") or "").strip()
      base = f"{mod}: {name}{sig}".strip()
      text = _wrap_one_line(f"{base}.", wrap)
      stubs.append({
        "tool": name,
        "module": mod,
        "signature": sig,
        "stub_line": f'  """{text}"""'
      })

    return {
      "ok": True,
      "missing_count": len(missing),
      "stubs": stubs
    }
