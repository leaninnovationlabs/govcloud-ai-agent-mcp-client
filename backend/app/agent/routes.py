from fastapi import APIRouter, Depends, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import json
import uuid

from ..core.config import get_settings, Settings
from ..core.response import APIResponse
from ..database.session import get_db_session
from .models import ChatRequest
from .service import AgentService

router = APIRouter()


def get_agent_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> AgentService:
    """Create agent service instance."""
    return AgentService(session, settings)


@router.post("/chat")
async def chat_message(
    request: Request,
    service: AgentService = Depends(get_agent_service),
) -> StreamingResponse:
    """Process chat message using graph-based agent with streaming response."""
    
    body = await request.body()
    
    try:
        request_data = json.loads(body)
        chat_request = ChatRequest(**request_data)
    except (json.JSONDecodeError, ValueError) as e:
        async def error_stream():
            error_response = {
                "blocks": [{"type": "text", "content": "Invalid request format. Please check your input."}],
                "message_id": str(uuid.uuid4()),
                "role": "ai"
            }
            yield json.dumps(error_response) + '\n'
        
        return StreamingResponse(
            error_stream(),
            media_type="application/x-ndjson",
            status_code=400,
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    
    async def generate_response():
        """Generator function to stream the response using proper pydantic-ai streaming."""
        accumulated_content = ""
        message_id = str(uuid.uuid4())
        
        try:
            # Use the fixed async generator directly
            async for text_delta in service.process_chat_message(
                chat_request.message, chat_request.conversation_id
            ):
                accumulated_content += text_delta
                
                response_data = {
                    "blocks": [{"type": "text", "content": accumulated_content}],
                    "message_id": message_id,
                    "role": "ai"
                }
                
                # Yield the data as a newline-delimited JSON string
                yield json.dumps(response_data) + '\n'
                
        except Exception as e:
            # Log the full error to the console for easier debugging
            print(f"[STREAMING ERROR] An exception occurred in generate_response: {e}")
            
            # Send a structured error back to the client
            error_response = {
                "blocks": [{"type": "text", "content": "I'm sorry, but an unexpected error occurred while processing your request."}],
                "message_id": message_id,
                "role": "ai",
                "error": str(e)
            }
            yield json.dumps(error_response) + '\n'
    
    return StreamingResponse(
        generate_response(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Content-Type-Options": "nosniff"
        },
    )

@router.get("/health")
async def health_check(
    settings: Settings = Depends(get_settings),
) -> APIResponse[dict]:
    """Health check endpoint."""
    
    health_status = {
        "status": "healthy",
        "agent_type": "graph_based",
        "model": settings.claude_model_id,
        "mcp_configured": bool(settings.mcp_server_url),
    }
    
    return APIResponse.success_response(health_status)