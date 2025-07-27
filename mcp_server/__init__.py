"""
Wikipedia MCP Server - Model Context Protocol server for Wikipedia integration.

This package provides a FastMCP-based server that exposes Wikipedia functionality
through the Model Context Protocol, enabling AI agents to search and retrieve
Wikipedia content in a standardized way.
"""

__version__ = "2.0.0"
__all__ = ["create_mcp_server", "WikipediaMCPServer", "WikipediaService"]

from .server import create_mcp_server, WikipediaMCPServer
from .wikipedia_service import WikipediaService