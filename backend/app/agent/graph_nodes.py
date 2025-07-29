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
    """Dependencies required by the graph nodes."""
    settings: Settings


class RouterNode(BaseNode[AgentState, GraphDependencies], LoggerMixin):
    """
    Determines the initial path of the user query based on whether
    it can be answered directly or requires tools.
    """
    def _get_agent(self, model_id: str) -> Agent:
        """Initializes and returns the routing agent."""
        return Agent(
            BedrockConverseModel(model_id),
            system_prompt="""Analyze the user query and available tools.
- If the query can be answered without tools, respond with: RESPONDER
- If the query requires external data or actions via tools, respond with: PLANNER

Your response must be a single word."""
        )

    async def run(self, ctx: GraphRunContext[AgentState, GraphDependencies]) -> Union[ResponderNode, PlannerNode]:
        """
        Executes the routing logic.

        This method inspects the user's query and the available tools. It uses an LLM
        to decide whether to route to the `PlannerNode` for tool usage or the
        `ResponderNode` for a direct answer. It also discovers available tools if they
        haven't been loaded into the state yet.
        """
        state = ctx.state
        with logfire.span(f"Running {self.__class__.__name__}", agent_state=state):
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
    """
    Creates a detailed, multi-step plan of tool calls required to address the user's request.
    """
    def _get_agent(self, model_id: str) -> Agent:
        """Initializes and returns the planning agent."""
        return Agent(
            BedrockConverseModel(model_id),
            output_type=PlannedToolCalls,
            system_prompt="""You are an expert planning agent. Analyze the user request and create a complete execution plan with ALL specific tool calls needed.

Your output must be a JSON object matching the PlannedToolCalls schema with ALL tool calls needed to complete the request.

Do NOT plan incrementally - determine the COMPLETE sequence of tool calls needed and return them all at once."""
        )

    def _flatten_schema_for_prompt(self, schema: dict) -> dict:
        """
        Simplifies a JSON schema for better LLM comprehension by removing
        unnecessary nesting around tool arguments.
        """
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
        """
        Executes the planning logic.

        This method constructs a detailed prompt including the user request and available
        tool schemas. It then uses an LLM to generate a complete sequence of tool calls.
        If no tools are needed, it transitions to the `ResponderNode`. Otherwise, it
        populates the state with pending tool calls and moves to the `ToolExecutorNode`.
        """
        state = ctx.state
        # state.clear_tool_history()
        with logfire.span(f"Running {self.__class__.__name__}", agent_state=state):
            self._log_info("Creating complete execution plan with tool calls", conversation_id=state.conversation_id)

            tools_for_prompt = []
            for tool in state.available_tools:
                tools_for_prompt.append({
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": self._flatten_schema_for_prompt(tool.input_schema)
                })

            schema_info = ""
            if state.schema_discovery_result:
                schema_info = f"\n\nDiscovered Schema: {json.dumps(state.schema_discovery_result, indent=2)}"
            
            error_info = ""
            if state.last_error:
                error_info = f"\n\nLast Error: {state.last_error}"


            planning_prompt = f"""
User Request: {state.user_message}

Available Tools (with schemas): {json.dumps(tools_for_prompt, indent=2)}
{schema_info}
{error_info}

Create a complete execution plan by determining ALL the specific tool calls needed to fulfill the user's request.
You MUST use the EXACT database, table, and column names from the Discovered Schema if it is provided. Do NOT hallucinate or guess any names.
This is a mission-critical life saving task that must be done correctly. Your previous errors have lead to the deaths 
of several people. You MUST get this right. Time is of the essence.

If a previous attempt failed, analyze the error and create a new plan to fix it.
- If the error is about a missing column or table, you MUST call `get_table_schema` to get the correct schema before generating a new query.
- If the query is invalid, you MUST generate a corrected query.
- Make sure that your planned tool calls use schema data that is up-to-date and accurate (check the state!!!).

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
    """
    Executes the planned tool calls in sequence.
    """
    async def run(self, ctx: GraphRunContext[AgentState, GraphDependencies]) -> ToolResultAnalyzerNode:
        """
        Executes the tool calls from the state.

        This method iterates through the `pending_tool_calls` in the agent state,
        executing each one via the `MCPClient`. It handles argument mapping,
        updates the status of each call (success or failure), and records the
        results or errors in the state. After execution, it transitions to the
        `ToolResultAnalyzerNode`.
        """
        state = ctx.state
        with logfire.span(f"Running {self.__class__.__name__}", agent_state=state):
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
                            
                            if tool_call.tool_name == 'discover_schema' and not result.get('isError'):
                                state.schema_discovery_result = result.get('structuredContent')

                            self._log_info(f"Tool '{tool_call.tool_name}' executed successfully with result: {result}")
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
            
            state.current_node = NodeType.TOOL_ANALYZER
            return ToolResultAnalyzerNode()




class ToolResultAnalyzerNode(BaseNode[AgentState, GraphDependencies], LoggerMixin):
    """
    Analyzes the results of tool execution and determines the next step.
    """
    def _get_agent(self, model_id: str) -> Agent:
        """Initializes and returns the analysis agent."""
        return Agent(
            BedrockConverseModel(model_id),
            system_prompt="""You are a tool result analyzer. Based on the completed tool calls, decide the next step.
- If all tools succeeded and the results are sufficient, respond with: RESPONDER
- If any tool failed, respond with: PLANNER to re-plan.
- If you need to retry a failed tool, respond with: RETRY

Your response must be a single word."""
        )

    async def run(self, ctx: GraphRunContext[AgentState, GraphDependencies]) -> Union[ResponderNode, PlannerNode, ToolExecutorNode]:
        """
        Executes the analysis logic.

        This method summarizes the results of the completed tool calls and asks an LLM
        to decide the next course of action. It can decide to re-plan (`PlannerNode`),
        retry failed calls (`ToolExecutorNode`), or proceed to generate a final
        response (`ResponderNode`).
        """
        state = ctx.state
        with logfire.span(f"Running {self.__class__.__name__}", agent_state=state):
            self._log_info("Analyzing tool results", conversation_id=state.conversation_id)

            completed_calls_summary = [
                {
                    "tool_name": call.tool_name,
                    "status": call.status.value,
                    "result": call.result,
                    "error": call.error
                } for call in state.completed_tool_calls
            ]

            schema_info = ""
            if state.schema_discovery_result:
                schema_info = f"\n\nDiscovered Schema: {json.dumps(state.schema_discovery_result, indent=2)}"
            
            analysis_prompt = f"""
User Request: {state.user_message}
Completed Tool Calls: {json.dumps(completed_calls_summary, indent=2)}
{schema_info}

Based on the results, what is the next step?
"""

            agent = self._get_agent(ctx.deps.settings.claude_model_id)
            result = await agent.run(analysis_prompt)
            next_node_str = result.output.strip().upper()

            if next_node_str == "PLANNER":
                state.current_node = NodeType.PLANNER
                self._log_info("Re-planning based on tool results", conversation_id=state.conversation_id)
                return PlannerNode()
            
            if next_node_str == "RETRY":
                state.current_node = NodeType.TOOL_EXECUTOR
                self._log_info("Retrying failed tool calls", conversation_id=state.conversation_id)
                state.retry_failed_calls()
                return ToolExecutorNode()

            state.current_node = NodeType.RESPONDER
            self._log_info("Proceeding to response", conversation_id=state.conversation_id)
            return ResponderNode()


class ResponderNode(BaseNode[AgentState, GraphDependencies, str], LoggerMixin):
    """
    Prepares the final context for the user response without making an LLM call itself.
    This node marks the end of the graph's execution.
    """

    async def run(self, ctx) -> End[str]:
        """
        Prepares the final context for streaming.

        This method gathers all the accumulated context from the agent state, including
        the initial user query and any information gathered from tool calls. It formats
        this context and stores it in the `final_response` field of the state, then
        ends the graph execution.
        """
        state = ctx.state
        with logfire.span(f"Running {self.__class__.__name__}", agent_state=state):
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