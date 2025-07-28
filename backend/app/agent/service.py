from __future__ import annotations

import asyncio
from functools import wraps
from typing import AsyncGenerator, Callable, Any
from contextlib import asynccontextmanager
from inspect import iscoroutinefunction

from pydantic_ai import Agent
from pydantic_ai.models.bedrock import BedrockConverseModel
from pydantic_graph import Graph
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import Settings
from ..core.exceptions import NotFoundError
from ..conversation.repository import ConversationRepository
from ..util.logging import LoggerMixin
from .models import MessageRole, MessageRead
from .repository import MessageRepository
from .state import AgentState
from .graph_nodes import (
    GraphDependencies,
    RouterNode,
    PlannerNode,
    ToolExecutorNode,
    ResponderNode,
)


def handle_exceptions(error_message: str = "An error occurred processing your request"):
    """Decorator for graceful error handling with logging."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            try:
                return await func(self, *args, **kwargs)
            except NotFoundError:
                raise  # Re-raise NotFoundErrors as they're expected
            except Exception as e:
                self._log_error(f"Error in {func.__name__}", exc_info=e)
                return error_message
        return wrapper
    return decorator


def log_execution_time(func: Callable) -> Callable:
    """Decorator to log execution time of methods."""
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        import time
        start_time = time.time()
        try:
            result = await func(self, *args, **kwargs)
            execution_time = time.time() - start_time
            self._log_info(f"{func.__name__} completed", execution_time_seconds=round(execution_time, 3))
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            self._log_error(f"{func.__name__} failed", execution_time_seconds=round(execution_time, 3), exc_info=e)
            raise
    return wrapper


class AgentService(LoggerMixin):
    """Production-quality agent service using proper graph execution patterns."""

    def __init__(self, session: AsyncSession, settings: Settings):
        super().__init__()
        self._session = session
        self._settings = settings
        self._message_repository = MessageRepository(session)
        self._conversation_repository = ConversationRepository(session)
        
        # Initialize the graph with proper nodes
        self._graph = Graph(
            nodes=[RouterNode, PlannerNode, ToolExecutorNode, ResponderNode]
        )
        
        # Create dependencies once for reuse
        self._graph_dependencies = GraphDependencies(settings=settings)
        
        self._log_info("AgentService initialized with production graph workflow")

    @property
    def graph(self) -> Graph:
        """Read-only access to the graph instance."""
        return self._graph

    @asynccontextmanager
    async def _conversation_context(self, conversation_id: int):
        """Context manager for conversation validation and cleanup."""
        conversation = await self._conversation_repository.get_conversation_by_id(conversation_id)
        if not conversation:
            raise NotFoundError("Conversation", conversation_id)
        
        self._log_info("Conversation context established", conversation_id=conversation_id)
        try:
            yield conversation
        finally:
            self._log_info("Conversation context cleaned up", conversation_id=conversation_id)

    async def _store_user_message(self, content: str, conversation_id: int) -> MessageRead:
        """Store user message and return the created message."""
        message = await self._message_repository.create_message(
            content, MessageRole.USER, conversation_id
        )
        self._log_info("User message stored", message_id=message.id, conversation_id=conversation_id)
        return message

    async def _store_assistant_message(self, content: str, conversation_id: int) -> MessageRead:
        """Store assistant message and return the created message."""
        message = await self._message_repository.create_message(
            content, MessageRole.ASSISTANT, conversation_id
        )
        self._log_info("Assistant message stored", message_id=message.id, conversation_id=conversation_id)
        return message

    async def process_chat_message(
        self, content: str, conversation_id: int
    ) -> AsyncGenerator[str, None]:
        """Process a chat message with proper pydantic-ai streaming."""
        import time
        start_time = time.time()
        
        try:
            async with self._conversation_context(conversation_id):
                # Store user message
                await self._store_user_message(content, conversation_id)
                
                # Execute graph to get tool results and context
                state = AgentState(conversation_id=conversation_id, user_message=content)
                self._log_info("Starting graph execution", conversation_id=conversation_id)
                
                # Run the graph to completion - start with RouterNode
                from .graph_nodes import RouterNode
                graph_result = await self._graph.run(RouterNode(), state=state, deps=self._graph_dependencies)
                
                # Use the context prepared by ResponderNode (stored in state.final_response)
                if state.final_response and state.final_response != "READY_FOR_STREAMING":
                    context = state.final_response
                    self._log_info("Using context prepared by ResponderNode", conversation_id=conversation_id)
                else:
                    # Fallback: prepare context if ResponderNode didn't set it properly
                    context_parts = [f"User Query: {state.user_message}"]
                    if state.accumulated_context:
                        context_parts.append("Information Gathered:")
                        context_parts.extend(state.accumulated_context)
                    context = "\n\n".join(context_parts)
                    self._log_info("Using fallback context preparation", conversation_id=conversation_id)
                
                # Create streaming agent using pydantic-ai pattern
                agent = Agent(
                    BedrockConverseModel(self._settings.claude_model_id),
                    system_prompt="You are a helpful AI assistant. Provide a comprehensive response to the user's query based on the available context and tool results."
                )
                
                response_content = ""
                self._log_info("Starting single LLM streaming call", conversation_id=conversation_id)
                
                # Single LLM call with proper streaming using TRUE deltas
                async with agent.run_stream(context) as result:
                    async for text_delta in result.stream_text(delta=True):
                        if text_delta:  # Only yield actual new content
                            response_content += text_delta
                            yield text_delta
                
                # Store complete assistant response
                await self._store_assistant_message(response_content, conversation_id)
                
                execution_time = time.time() - start_time
                self._log_info("Chat message processing completed", 
                              conversation_id=conversation_id, 
                              response_length=len(response_content),
                              execution_time_seconds=round(execution_time, 3))
                              
        except NotFoundError:
            raise  # Re-raise NotFoundErrors as they're expected
        except Exception as e:
            execution_time = time.time() - start_time
            self._log_error("Error in process_chat_message", 
                           exc_info=e, 
                           execution_time_seconds=round(execution_time, 3))
            yield "I encountered an error processing your request. Please try again."

    @handle_exceptions()
    @log_execution_time
    async def list_conversations(self) -> list['ConversationRead']:
        """List all conversations with proper error handling."""
        from ..conversation.models import ConversationRead
        conversations = await self._conversation_repository.get_all_conversations()
        # Convert to serializable ConversationRead objects
        conversation_data = [ConversationRead.model_validate(conv) for conv in conversations]
        self._log_info("Listed conversations", count=len(conversation_data))
        return conversation_data

    @handle_exceptions()
    @log_execution_time
    async def get_conversation_messages(self, conversation_id: int) -> list[MessageRead]:
        """Get all messages in a conversation with validation."""
        async with self._conversation_context(conversation_id):
            messages = await self._message_repository.get_messages_by_conversation_id(conversation_id)
            self._log_info("Retrieved conversation messages", 
                          conversation_id=conversation_id, 
                          message_count=len(messages))
            return messages

    def __repr__(self) -> str:
        """Professional string representation for debugging."""
        return f"AgentService(session={self._session!r}, settings={self._settings!r})"