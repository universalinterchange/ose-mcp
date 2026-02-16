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

  mcp.run()  # stdio transport for Claude Desktop

if __name__ == "__main__":
  main()
