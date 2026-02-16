from mcp.server.fastmcp import FastMCP

from ose_mcp.modules.mechanics import register_mechanics
from ose_mcp.modules.procedures import register_procedures
from ose_mcp.modules.stocking import register_stocking
from ose_mcp.modules.state import register_state
from ose_mcp.modules.refs import register_refs
from ose_mcp.modules.oracle import register_oracle
from ose_mcp.modules.encounters import register_encounters
from ose_mcp.modules.world import register_world
from ose_mcp.modules.travel import register_travel
from ose_mcp.modules.loot import register_loot
from ose_mcp.modules.gm import register_gm
from ose_mcp.modules.tables import register_tables
from ose_mcp.modules.progression import register_progression
from ose_mcp.modules.encumbrance import register_encumbrance
from ose_mcp.modules.light import register_light
from ose_mcp.modules.magic import register_magic
from ose_mcp.modules.hirelings import register_hirelings
from ose_mcp.modules.economy import register_economy
from ose_mcp.modules.adventures import register_adventures
from ose_mcp.modules.consequences import register_consequences
from ose_mcp.modules.help import register_help

mcp = FastMCP(name="ose-mcp")

def main():
  register_mechanics(mcp)
  register_procedures(mcp)
  register_stocking(mcp)
  register_state(mcp)
  register_refs(mcp)
  register_oracle(mcp)
  register_encounters(mcp)
  register_world(mcp)
  register_travel(mcp)
  register_loot(mcp)
  register_gm(mcp)
  register_tables(mcp)
  register_progression(mcp)
  register_encumbrance(mcp)
  register_light(mcp)
  register_magic(mcp)
  register_hirelings(mcp)
  register_economy(mcp)
  register_adventures(mcp)
  register_consequences(mcp)
  register_help(mcp)

  mcp.run()  # stdio transport for Claude Desktop

if __name__ == "__main__":
  main()
