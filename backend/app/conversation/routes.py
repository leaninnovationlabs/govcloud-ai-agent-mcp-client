from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from ..agent.repository import MessageRepository
from ..agent.models import MessageRead

from ..agent.models import MessageRead
from ..core.response import APIResponse
from ..database.session import get_db_session
from .models import ConversationRead
from .service import ConversationService

router = APIRouter()


@router.post(
    "/new", 
    response_model=APIResponse[ConversationRead],
    status_code=status.HTTP_201_CREATED
)
async def create_conversation(
    session: AsyncSession = Depends(get_db_session),
) -> APIResponse[ConversationRead]:
    service = ConversationService(session)
    conversation = await service.create_new_conversation()
    return APIResponse.success_response(conversation)


@router.get("/", response_model=APIResponse[list[ConversationRead]])
async def get_conversations(
    session: AsyncSession = Depends(get_db_session),
) -> APIResponse[list[ConversationRead]]:
    service = ConversationService(session)
    conversations = await service.get_all_conversations()
    return APIResponse.success_response(conversations)


@router.get(
    "/{conversation_id}", 
    response_model=APIResponse[ConversationRead]
)
async def get_conversation(
    conversation_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> APIResponse[ConversationRead]:
    service = ConversationService(session)
    conversation = await service.get_conversation_by_id(conversation_id)
    return APIResponse.success_response(conversation)


@router.get(
    "/{conversation_id}/messages", 
    response_model=APIResponse[list[MessageRead]]
)
async def get_conversation_messages(
    conversation_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> APIResponse[list[MessageRead]]:
    message_repository = MessageRepository(session)
    messages = await message_repository.get_messages_by_conversation_id(conversation_id)
    
    # Convert to read models
    message_data = [MessageRead.model_validate(msg) for msg in messages]
    
    return APIResponse.success_response(message_data) 