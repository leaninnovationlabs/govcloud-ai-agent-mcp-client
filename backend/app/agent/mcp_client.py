from __future__ import annotations

import json
import uuid
from typing import Any, Optional

import httpx
from pydantic import BaseModel, ValidationError

from ..util.logging import LoggerMixin
from .state import MCPTool, ToolCall


class MCPInitializeRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str
    method: str = "initialize"
    params: dict[str, Any]


class MCPInitializeResult(BaseModel):
    protocolVersion: str
    capabilities: dict[str, Any]
    serverInfo: dict[str, Any]


class MCPListToolsRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str
    method: str = "tools/list"
    params: dict[str, Any] = {}


class MCPCallToolRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str
    method: str = "tools/call"
    params: dict[str, Any]


class MCPResponse(BaseModel):
    jsonrpc: str
    id: str
    result: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None


class MCPClient(LoggerMixin):
    def __init__(self, server_url: str, timeout: float = 30.0):
        super().__init__()
        self.server_url = server_url.rstrip('/')
        self.session_id: Optional[str] = None
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)
        self._initialized = False
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    async def close(self):
        await self.client.aclose()
        
    async def initialize(self) -> MCPInitializeResult:
        """Initialize connection with MCP server using Streamable HTTP transport."""
        if self._initialized:
            return
            
        request_id = str(uuid.uuid4())
        request = MCPInitializeRequest(
            id=request_id,
            params={
                "protocolVersion": "2025-03-26",
                "capabilities": {
                    "tools": {"listChanged": True}
                },
                "clientInfo": {
                    "name": "govcloud-ai-agent",
                    "version": "1.0.0"
                }
            }
        )
        
        self._log_info("Initializing MCP connection", server_url=self.server_url)
        
        response = await self._make_request(request.model_dump(by_alias=True))
        
        if response.error:
            raise Exception(f"MCP initialization failed: {response.error}")
            
        result = MCPInitializeResult(**response.result)
            
        self._initialized = True
        self._log_info("MCP initialization successful", 
                      protocol_version=result.protocolVersion,
                      server_name=result.serverInfo.get('name', 'unknown'))
        
        return result
        
    async def list_tools(self) -> list[MCPTool]:
        """Discover available tools from MCP server."""
        if not self._initialized:
            await self.initialize()
            
        self._log_info("Discovering tools from MCP server")
        
        try:
            request = MCPListToolsRequest(id=str(uuid.uuid4()))
            response = await self._make_request(request.model_dump(by_alias=True))
            
            if response.error:
                raise Exception(f"Tool discovery failed: {response.error}")

            self._log_info(f"Tools list response: {response.result}")
                
            tools_data = response.result.get('tools', [])
            tools = [MCPTool(**tool_data) for tool_data in tools_data]
                
            self._log_info("Tools discovered successfully", tool_count=len(tools),
                        tool_names=[t.name for t in tools])
            
            return tools
            
        except Exception as e:
            self._log_error("Tool discovery failed", error=str(e))
            raise Exception(f"Tool discovery failed: {e}")
        
    async def call_tool(self, tool_call: ToolCall) -> dict[str, Any]:
        """Execute a tool call via MCP server."""
        if not self._initialized:
            await self.initialize()
            
        request = MCPCallToolRequest(
            id=tool_call.id,
            params={
                "name": tool_call.tool_name,
                "arguments": tool_call.arguments
            }
        )
        
        self._log_info("Executing tool call", 
                      tool_name=tool_call.tool_name,
                      call_id=tool_call.id,
                      arguments=tool_call.arguments)
        
        response = await self._make_request(request.model_dump(by_alias=True))
        
        if response.error:
            self._log_error("Tool execution failed",
                          tool_name=tool_call.tool_name,
                          call_id=tool_call.id,
                          error=response.error)
            raise Exception(f"Tool execution failed: {response.error}")
            
        result = response.result
        
        self._log_info("Tool execution successful",
                      tool_name=tool_call.tool_name,
                      call_id=tool_call.id,
                      result_keys=list(result.keys()) if result else [])
        
        return result
        
    async def _make_request(self, payload: dict[str, Any]) -> MCPResponse:
        """Make HTTP request to MCP server, properly handling SSE streams."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
            
        try:
            response = await self.client.post(
                f"{self.server_url}/mcp/",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            
            if 'Mcp-Session-Id' in response.headers:
                self.session_id = response.headers['Mcp-Session-Id']
                self._log_info("MCP session ID updated", session_id=self.session_id)
                
            content_type = response.headers.get('content-type', '')
            
            # If the response is an event stream, parse it correctly.
            if 'text/event-stream' in content_type:
                return self._parse_sse_response(response.text, payload.get("id"))
            
            # Otherwise, handle it as a simple JSON response.
            return MCPResponse(**response.json())
            
        except httpx.TimeoutException:
            self._log_error("MCP request timeout", server_url=self.server_url)
            raise
        except httpx.HTTPStatusError as e:
            self._log_error("MCP HTTP error", 
                          status_code=e.response.status_code,
                          response_text=e.response.text)
            raise
        except Exception as e:
            self._log_error("MCP request failed", error_type=type(e).__name__, error=str(e))
            raise

    def _parse_sse_response(self, text: str, request_id: str) -> MCPResponse:
        """
        Parses a Server-Sent Events (SSE) stream.
        It logs notifications and returns the first valid response matching the request ID.
        """
        for line in text.strip().split('\n'):
            if not line.startswith('data:'):
                continue

            try:
                data_str = line[5:].strip()
                json_data = json.loads(data_str)

                # A notification has a 'method' but no 'id'. Log it and continue.
                if 'method' in json_data and 'id' not in json_data:
                    self._log_info("Received MCP notification",
                                   method=json_data.get('method'),
                                   params=json_data.get('params'))
                    continue

                # A response has an 'id'. Check if it's the one we're waiting for.
                if json_data.get('id') == request_id:
                    return MCPResponse(**json_data)

            except (json.JSONDecodeError, ValidationError) as e:
                self._log_warning("Failed to parse SSE event", data=data_str, error=str(e))
                continue
        
        raise Exception(f"No valid response found in SSE stream for request ID {request_id}")
