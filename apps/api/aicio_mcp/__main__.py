"""MCP stdio server — run with: PYTHONPATH=apps/api python -m aicio_mcp"""
from aicio_mcp.server import mcp

if __name__ == "__main__":
    mcp.run()
