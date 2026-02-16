import inspect
from typing import Any

def register_help(mcp):
  tool_names: list[str] = []
  tool_registrations: list[str] = []
  tool_meta: dict[str, dict[str, Any]] = {}

  orig_tool = mcp.tool

  def _short_module(mod: str) -> str:
    # 'ose_mcp.modules.world' -> 'world'
    if not mod:
      return "unknown"
    parts = mod.split(".")
    return parts[-1]

  def _capture(fn, name: str):
    sig = ""
    try:
      sig = str(inspect.signature(fn))
    except Exception:
      sig = ""

    desc = (fn.__doc__ or "").strip() if hasattr(fn, "__doc__") else ""
    mod = _short_module(getattr(fn, "__module__", ""))

    tool_names.append(name)
    tool_registrations.append(name)

    tool_meta[name] = {
      "name": name,
      "module": mod,
      "signature": sig,
      "description": desc
    }

    # Expose for other modules (ops.lint_tools)
    mcp._ose_tool_names = tool_names
    mcp._ose_tool_registrations = tool_registrations
    mcp._ose_tool_meta = tool_meta

  def _group_by_module(names: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for n in names:
      mod = tool_meta.get(n, {}).get("module", "unknown")
      grouped.setdefault(mod, []).append(n)
    for k in grouped:
      grouped[k].sort()
    return dict(sorted(grouped.items(), key=lambda kv: kv[0]))

  def _group_by_prefix(names: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for n in names:
      prefix = n.split("_", 1)[0] if "_" in n else "misc"
      grouped.setdefault(prefix, []).append(n)
    for k in grouped:
      grouped[k].sort()
    return dict(sorted(grouped.items(), key=lambda kv: kv[0]))

  # Help tools registered with original decorator
  @orig_tool()
  def ose_help(view: str = "module") -> dict[str, Any]:
    """
    List available tools.
    view='module' groups by python module (recommended)
    view='prefix' groups by name prefix (legacy)
    """
    names = sorted(set(tool_names))
    v = (view or "module").strip().lower()
    if v == "prefix":
      grouped = _group_by_prefix(names)
    else:
      grouped = _group_by_module(names)

    return {
      "ok": True,
      "tool_count": len(names),
      "view": v,
      "modules": {k: len(v) for k, v in grouped.items()},
      "grouped": grouped
    }

  @orig_tool()
  def ose_help_module(module: str) -> dict[str, Any]:
    """
    Show tools for a python module name, e.g. 'world', 'state', 'tables'.
    """
    mod = (module or "").strip().lower()
    names = sorted(set(tool_names))
    matched = [n for n in names if tool_meta.get(n, {}).get("module", "").lower() == mod]
    return {
      "ok": True,
      "module": mod,
      "count": len(matched),
      "tools": [tool_meta.get(n, {"name": n}) for n in matched]
    }

  @orig_tool()
  def ose_help_tool(name: str) -> dict[str, Any]:
    """
    Show one tool by exact name; returns suggestions if not found.
    """
    nm = (name or "").strip()
    names = sorted(set(tool_names))
    if nm not in tool_meta:
      sugg = [n for n in names if nm.lower() in n.lower()]
      return {"ok": False, "error": "tool not found", "query": name, "suggestions": sugg[:50]}
    return {"ok": True, "tool": tool_meta[nm]}

  @orig_tool()
  def ose_help_search(query: str, limit: int = 25) -> dict[str, Any]:
    """
    Search tools by name + description.
    """
    q = (query or "").strip().lower()
    lim = max(1, min(200, int(limit)))
    if not q:
      return {"ok": False, "error": "empty query"}
    names = sorted(set(tool_names))
    hits = []
    for n in names:
      meta = tool_meta.get(n, {"name": n, "signature": "", "description": "", "module": "unknown"})
      hay = (n + "\n" + (meta.get("description") or "")).lower()
      if q in hay:
        hits.append(meta)
    hits.sort(key=lambda x: x.get("name", ""))
    return {"ok": True, "query": query, "count": len(hits), "results": hits[:lim]}

  @orig_tool()
  def ose_help_debug() -> dict[str, Any]:
    """
    Debug: show how many tools have been captured so far.
    """
    names = sorted(set(tool_names))
    mods = {}
    for n in names:
      mods[tool_meta.get(n, {}).get("module", "unknown")] = mods.get(tool_meta.get(n, {}).get("module", "unknown"), 0) + 1
    return {"ok": True, "captured": len(names), "modules": dict(sorted(mods.items())), "sample": names[:50]}

  # Wrap mcp.tool to capture all tools registered after register_help()
  def tool_wrapper(*args, **kwargs):
    decorator = orig_tool(*args, **kwargs)

    def inner(fn):
      name = kwargs.get("name") if isinstance(kwargs, dict) else None
      if not name:
        name = getattr(fn, "__name__", "unknown_tool")
      _capture(fn, name)
      return decorator(fn)

    return inner

  mcp.tool = tool_wrapper
