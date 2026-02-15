from mcp.server.fastmcp import FastMCP

from ose_mcp.modules.mechanics import register_mechanics
from ose_mcp.modules.state import register_state
from ose_mcp.modules.refs import register_refs

mcp = FastMCP(name="ose-mcp", version="0.1.0")

def main():
    # register tool modules
    register_mechanics(mcp)
    register_state(mcp)
    register_refs(mcp)

    # stdio is what Claude Desktop expects for local servers
    mcp.run()

if __name__ == "__main__":
    main()

