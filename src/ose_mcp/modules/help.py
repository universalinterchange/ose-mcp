import inspect
from typing import Any

def _tool_registry(mcp) -> dict[str, Any]:
  """
  FastMCP internal registry varies by version. Try common locations.
  Returns dict-like mapping of tool_name -> tool_object.
  """
  for attr in ("_tools", "tools", "_tool_map", "_registry"):
    reg = getattr(mcp, attr, None)
    if isinstance(reg, dict) and reg:
      return reg
  # Some versions keep a list/iterable; normalize if possible
  reg = getattr(mcp, "_tools", None)
  if isinstance(reg, dict):
    return reg
  return {}

def _tool_callable(tool_obj: Any):
  """
  Try to extract the underlying function for signature/doc.
  Tool wrappers differ across versions.
  """
  for attr in ("fn", "func", "function", "_fn", "_func", "callable"):
    f = getattr(tool_obj, attr, None)
    if callable(f):
      return f
  # If tool_obj itself is callable, use it
  if callable(tool_obj):
    return tool_obj
  return None

def _tool_description(tool_obj: Any) -> str:
  for attr in ("description", "__doc__"):
    d = getattr(tool_obj, attr, None)
    if isinstance(d, str) and d.strip():
      return d.strip()
  f = _tool_callable(tool_obj)
  if f and isinstance(getattr(f, "__doc__", None), str):
    return (f.__doc__ or "").strip()
  return ""

def _tool_signature(tool_obj: Any) -> str:
  f = _tool_callable(tool_obj)
  if not f:
    return ""
  try:
    return str(inspect.signature(f))
  except Exception:
    return ""

def _group_tools(names: list[str]) -> dict[str, list[str]]:
  groups: dict[str, list[str]] = {}
  for n in names:
    prefix = n.split("_", 1)[0] if "_" in n else "misc"
    groups.setdefault(prefix, []).append(n)
  for k in groups:
    groups[k].sort()
  return dict(sorted(groups.items(), key=lambda kv: kv[0]))

def register_help(mcp):

  @mcp.tool()
  def help() -> dict[str, Any]:
    """
    Show an overview of all available tools.
    Tools are grouped by the prefix before the first underscore, e.g. 'world_*'.
    """
    reg = _tool_registry(mcp)
    names = sorted(list(reg.keys()))
    grouped = _group_tools(names)
    return {
      "tool_count": len(names),
      "modules": {k: len(v) for k, v in grouped.items()},
      "grouped": grouped
    }

  @mcp.tool()
  def help_module(module: str) -> dict[str, Any]:
    """
    List tools in a module group (prefix before underscore).
    Example: help_module("world") returns all world_* tools.
    """
    mod = (module or "").strip().lower()
    reg = _tool_registry(mcp)
    names = sorted(list(reg.keys()))
    matched = [n for n in names if (n.split("_", 1)[0].lower() == mod)]
    tools = []
    for n in matched:
      t = reg.get(n)
      tools.append({
        "name": n,
        "signature": _tool_signature(t),
        "description": _tool_description(t),
      })
    return {
      "module": mod,
      "count": len(matched),
      "tools": tools
    }

  @mcp.tool()
  def help_tool(name: str) -> dict[str, Any]:
    """
    Show details for a single tool by exact name.
    Example: help_tool("random_encounter")
    """
    nm = (name or "").strip()
    reg = _tool_registry(mcp)
    if nm not in reg:
      # try case-insensitive / partial fallback
      keys = sorted(reg.keys())
      near = [k for k in keys if k.lower() == nm.lower()]
      if near:
        nm = near[0]
      else:
        partial = [k for k in keys if nm.lower() in k.lower()]
        return {
          "ok": False,
          "error": "tool not found",
          "query": name,
          "suggestions": partial[:25]
        }
    t = reg[nm]
    return {
      "ok": True,
      "name": nm,
      "signature": _tool_signature(t),
      "description": _tool_description(t),
    }

  @mcp.tool()
  def help_search(query: str, limit: int = 25) -> dict[str, Any]:
    """
    Search tools by name and docstring.
    """
    q = (query or "").strip().lower()
    lim = max(1, min(200, int(limit)))
    reg = _tool_registry(mcp)
    if not q:
      return {"ok": False, "error": "empty query"}

    hits = []
    for name, t in reg.items():
      desc = _tool_description(t)
      hay = (name + "\n" + desc).lower()
      if q in hay:
        hits.append({
          "name": name,
          "signature": _tool_signature(t),
          "description": desc
        })

    hits.sort(key=lambda x: x["name"])
    return {
      "ok": True,
      "query": query,
      "count": len(hits),
      "results": hits[:lim]
    }

  @mcp.tool()
  def help_markdown() -> dict[str, Any]:
    """
    Return the help overview as Markdown text (nice for copying).
    """
    reg = _tool_registry(mcp)
    names = sorted(list(reg.keys()))
    grouped = _group_tools(names)

    lines = []
    lines.append(f"# ose-mcp help")
    lines.append(f"- tools: **{len(names)}**")
    lines.append("")
    for mod, tools in grouped.items():
      lines.append(f"## {mod} ({len(tools)})")
      for n in tools:
        t = reg.get(n)
        sig = _tool_signature(t)
        desc = _tool_description(t)
        first = desc.splitlines()[0] if desc else ""
        if sig:
          lines.append(f"- `{n}{sig}` — {first}")
        else:
          lines.append(f"- `{n}` — {first}")
      lines.append("")
    return {"ok": True, "markdown": "\n".join(lines)}
