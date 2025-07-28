"""
Athena MCP Server - Model Context Protocol server for AWS Athena data lake querying.

This package provides a FastMCP-based server that exposes AWS Athena functionality
through the Model Context Protocol, enabling AI agents to discover schemas and
execute queries against data lakes in a standardized way.
"""

__version__ = "1.0.0"
__all__ = ["create_mcp_server", "AthenaMCPServer", "AthenaService"]

from .server import create_mcp_server, AthenaMCPServer
from .athena_service import AthenaService