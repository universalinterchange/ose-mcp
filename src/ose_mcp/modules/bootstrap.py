from typing import Any

from ose_mcp.modules.state import init_state
from ose_mcp.modules.procedures import init_procedures
from ose_mcp.modules.world import init_world
from ose_mcp.modules.tables import init_tables
from ose_mcp.modules.encumbrance import init_encumbrance
from ose_mcp.modules.light import init_light
from ose_mcp.modules.magic import init_magic
from ose_mcp.modules.hirelings import init_hirelings
from ose_mcp.modules.economy import init_economy
from ose_mcp.modules.adventures import init_adventures
from ose_mcp.modules.consequences import init_consequences
from ose_mcp.modules.oracle import init_oracle
from ose_mcp.modules.refs import init_refs

def register_bootstrap(mcp):

  @mcp.tool()
  def init_all(include_refs: bool = True, chaos: int = 5) -> dict[str, Any]:
    """
    Initialize all campaign tables (and optionally refs).
    Safe to run multiple times.
    """
    results = {}

    results["state_init"] = init_state()
    results["proc_init"] = init_procedures()
    results["world_init"] = init_world()
    results["tables_init"] = init_tables()
    results["encumbrance_init"] = init_encumbrance()
    results["light_init"] = init_light()
    results["magic_init"] = init_magic()
    results["hirelings_init"] = init_hirelings()
    results["economy_init"] = init_economy()
    results["adventures_init"] = init_adventures()
    results["consequences_init"] = init_consequences()
    results["oracle_init"] = init_oracle(chaos=chaos)

    if include_refs:
      results["refs_init"] = init_refs()

    return {"ok": True, "results": results}
