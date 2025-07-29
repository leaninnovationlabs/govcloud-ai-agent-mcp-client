from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict


class NodeType(str, Enum):
    """Enumeration for the different nodes in the agent graph."""
    ROUTER = "router"
    PLANNER = "planner"
    TOOL_EXECUTOR = "tool_executor"
    TOOL_ANALYZER = "tool_analyzer"
    RESPONDER = "responder"


class ToolCallStatus(str, Enum):
    """Enumeration for the status of a tool call."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class MCPTool(BaseModel):
    """Represents a tool available via the MCP server."""
    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict, alias="inputSchema")


class ToolCall(BaseModel):
    """Represents a single, planned tool call."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str
    arguments: dict[str, Any]
    status: ToolCallStatus = ToolCallStatus.PENDING
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class Plan(BaseModel):
    """Represents the multi-step plan created by the planning agent."""
    steps: list[str] = Field(description="Ordered list of steps to accomplish the task.")
    required_tools: list[str] = Field(description="Tools needed for this plan.")
    reasoning: str = Field(description="Why this plan will accomplish the task.")


class PlannedToolCalls(BaseModel):
    """Structured output from the tool execution planner."""
    tool_calls: list[ToolCall] = Field(description="A list of specific tool calls to be executed.")


@dataclass
class AgentState:
    """The central state object that is passed through the graph."""
    conversation_id: int
    user_message: str
    available_tools: list[MCPTool] = field(default_factory=list)
    current_plan: Optional[Plan] = None
    pending_tool_calls: list[ToolCall] = field(default_factory=list)
    completed_tool_calls: list[ToolCall] = field(default_factory=list)
    accumulated_context: list[str] = field(default_factory=list)
    final_response: Optional[str] = None
    current_node: NodeType = NodeType.ROUTER
    created_at: datetime = field(default_factory=datetime.utcnow)
    schema_discovery_result: Optional[dict[str, Any]] = None
    last_error: Optional[str] = None

    def add_context(self, context: str) -> None:
        """Appends a string to the accumulated context."""
        self.accumulated_context.append(context)

    def complete_tool_call(self, call_id: str, result: dict[str, Any]) -> None:
        """Marks a pending tool call as completed and moves it to the completed list."""
        for call in self.pending_tool_calls:
            if call.id == call_id:
                call.status = ToolCallStatus.COMPLETED
                call.result = result
                self.completed_tool_calls.append(call)
                self.pending_tool_calls.remove(call)
                break

    def fail_tool_call(self, call_id: str, error: str) -> None:
        """Marks a pending tool call as failed and moves it to the completed list."""
        for call in self.pending_tool_calls:
            if call.id == call_id:
                call.status = ToolCallStatus.FAILED
                call.error = error
                self.completed_tool_calls.append(call)
                self.pending_tool_calls.remove(call)
                self.last_error = error
                break
    
    def retry_failed_calls(self) -> None:
        """Moves failed calls back to the pending list for a retry."""
        failed_calls = [call for call in self.completed_tool_calls if call.status == ToolCallStatus.FAILED]
        for call in failed_calls:
            call.status = ToolCallStatus.PENDING
            call.error = None
            self.pending_tool_calls.append(call)
            self.completed_tool_calls.remove(call)

    def clear_tool_history(self) -> None:
        """Clears the history of completed tool calls."""
        self.completed_tool_calls = []