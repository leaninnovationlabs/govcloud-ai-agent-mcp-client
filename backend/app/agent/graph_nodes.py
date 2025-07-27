from __future__ import annotations
import uuid
import json
from dataclasses import dataclass
from typing import Union

import logfire
from pydantic_ai import Agent
from pydantic_ai.models.bedrock import BedrockConverseModel
from pydantic_graph import BaseNode, End, GraphRunContext

from ..core.config import Settings
from ..util.logging import LoggerMixin
from .mcp_client import MCPClient
from .state import AgentState, NodeType, ToolCall, ToolCallStatus, PlannedToolCalls


@dataclass
class GraphDependencies:
    settings: Settings


class RouterNode(BaseNode[AgentState, GraphDependencies], LoggerMixin):
    def _get_agent(self, model_id: str) -> Agent:
        return Agent(
            BedrockConverseModel(model_id),
            system_prompt="""Analyze the user query and available tools.
- If the query can be answered without tools, respond with: RESPONDER
- If the query requires external data or actions via tools, respond with: PLANNER

Your response must be a single word."""
        )

    async def run(self, ctx: GraphRunContext[AgentState, GraphDependencies]) -> Union[ResponderNode, PlannerNode]:
        state = ctx.state
        self._log_info("Routing user query", conversation_id=state.conversation_id)

        if not state.available_tools:
            with logfire.span("discovering_tools"):
                async with MCPClient(ctx.deps.settings.mcp_server_url) as mcp:
                    state.available_tools = await mcp.list_tools()
                    self._log_info("Discovered tools", tool_count=len(state.available_tools))

        tool_info = f"Available tools: {[t.name for t in state.available_tools]}"
        routing_prompt = f"Query: {state.user_message}\n\n{tool_info}"

        agent = self._get_agent(ctx.deps.settings.claude_model_id)
        result = await agent.run(routing_prompt)
        next_node_str = result.output.strip().upper()

        if next_node_str == "RESPONDER":
            state.current_node = NodeType.RESPONDER
            self._log_info("Routing to direct response", conversation_id=state.conversation_id)
            return ResponderNode()
        
        state.current_node = NodeType.PLANNER
        self._log_info("Routing to planner", conversation_id=state.conversation_id)
        return PlannerNode()


class PlannerNode(BaseNode[AgentState, GraphDependencies], LoggerMixin):
    def _get_agent(self, model_id: str) -> Agent:
        return Agent(
            BedrockConverseModel(model_id),
            output_type=PlannedToolCalls,
            system_prompt="""You are an expert planning agent. Analyze the user request and create a complete execution plan with ALL specific tool calls needed.

Your output must be a JSON object matching the PlannedToolCalls schema with ALL tool calls needed to complete the request.

Do NOT plan incrementally - determine the COMPLETE sequence of tool calls needed and return them all at once."""
        )

    def _flatten_schema_for_prompt(self, schema: dict) -> dict:
        if (
            isinstance(schema.get('properties'), dict) and
            'args' in schema['properties'] and
            isinstance(schema['properties']['args'], dict) and
            '$ref' in schema['properties']['args']
        ):
            try:
                ref_path = schema['properties']['args']['$ref']
                model_name = ref_path.split('/')[-1]
                if model_name in schema.get('$defs', {}):
                    return schema['$defs'][model_name]
            except (KeyError, IndexError):
                pass
        return schema

    async def run(self, ctx: GraphRunContext[AgentState, GraphDependencies]) -> Union[ToolExecutorNode, ResponderNode]:
        state = ctx.state
        self._log_info("Creating complete execution plan with tool calls", conversation_id=state.conversation_id)

        tools_for_prompt = []
        for tool in state.available_tools:
            tools_for_prompt.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": self._flatten_schema_for_prompt(tool.input_schema)
            })

        planning_prompt = f"""
User Request: {state.user_message}

Available Tools (with schemas): {json.dumps(tools_for_prompt, indent=2)}

Create a complete execution plan by determining ALL the specific tool calls needed to fulfill the user's request. 
Return them as a single JSON object with all tool calls that should be executed in sequence.

If no tools are needed, return: {{"tool_calls": []}}
"""

        agent = self._get_agent(ctx.deps.settings.claude_model_id)
        result = await agent.run(planning_prompt)
        planned_calls = result.output

        if not planned_calls.tool_calls:
            state.current_node = NodeType.RESPONDER
            self._log_info("No tools needed, proceeding to response", conversation_id=state.conversation_id)
            return ResponderNode()

        state.pending_tool_calls.extend(planned_calls.tool_calls)
        state.current_node = NodeType.TOOL_EXECUTOR
        
        logfire.info("Complete plan created", calls=[c.model_dump() for c in planned_calls.tool_calls])
        self._log_info("Complete execution plan created", 
                      conversation_id=state.conversation_id, 
                      total_tool_calls=len(planned_calls.tool_calls))
        return ToolExecutorNode()


class ToolExecutorNode(BaseNode[AgentState, GraphDependencies], LoggerMixin):
    async def run(self, ctx: GraphRunContext[AgentState, GraphDependencies]) -> Union[ResponderNode, 'ToolExecutorNode']:
        state = ctx.state
        
        if not state.pending_tool_calls:
            state.current_node = NodeType.RESPONDER
            self._log_info("All tool calls completed, proceeding to response", conversation_id=state.conversation_id)
            return ResponderNode()

        self._log_info("Executing tool calls", conversation_id=state.conversation_id, count=len(state.pending_tool_calls))

        tool_schema_map = {tool.name: tool.input_schema for tool in state.available_tools}
        completed_this_batch = []

        async with MCPClient(ctx.deps.settings.mcp_server_url) as mcp:
            for tool_call in state.pending_tool_calls[:]:
                with logfire.span("executing_tool", tool_name=tool_call.tool_name, tool_call=tool_call.model_dump()) as span:
                    try:
                        original_schema = tool_schema_map.get(tool_call.tool_name, {})
                        arguments_to_send = tool_call.arguments

                        if (
                            isinstance(original_schema.get('properties'), dict) and
                            'args' in original_schema['properties']
                        ):
                            arguments_to_send = {"args": tool_call.arguments}

                        call_to_execute = ToolCall(
                            id=tool_call.id,
                            tool_name=tool_call.tool_name,
                            arguments=arguments_to_send
                        )

                        tool_call.status = ToolCallStatus.EXECUTING
                        result = await mcp.call_tool(call_to_execute)
                        
                        span.set_attribute("result", result)
                        state.complete_tool_call(tool_call.id, result)
                        context_entry = f"Tool '{tool_call.tool_name}' result: {result}"
                        state.add_context(context_entry)
                        completed_this_batch.append(tool_call.id)
                        
                    except Exception as e:
                        span.set_attribute("error", str(e))
                        self._log_error("Tool execution failed", tool_name=tool_call.tool_name, error=str(e))
                        state.fail_tool_call(tool_call.id, str(e))
                        state.add_context(f"Tool '{tool_call.tool_name}' failed with error: {e}")
                        completed_this_batch.append(tool_call.id)

        self._log_info("Tool execution batch completed", 
                      conversation_id=state.conversation_id, 
                      completed_count=len(completed_this_batch),
                      remaining_count=len(state.pending_tool_calls))
        
        return ToolExecutorNode() if state.pending_tool_calls else ResponderNode()


class ResponderNode(BaseNode[AgentState, GraphDependencies, str], LoggerMixin):
    """Efficient ResponderNode that prepares context for streaming without making an LLM call."""

    async def run(self, ctx) -> End[str]:
        state = ctx.state
        self._log_info("Preparing context for streaming response", conversation_id=state.conversation_id)

        context_parts = [f"User Query: {state.user_message}"]
        if state.accumulated_context:
            context_parts.append("Information Gathered:")
            context_parts.extend(state.accumulated_context)

        # Store the prepared context in final_response for the service to use
        prepared_context = "\n\n".join(context_parts)
        state.final_response = prepared_context

        self._log_info("Context prepared for streaming", 
                      conversation_id=state.conversation_id, 
                      context_length=len(prepared_context))
        
        return End("READY_FOR_STREAMING")