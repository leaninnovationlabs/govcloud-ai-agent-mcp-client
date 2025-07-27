from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import NotFoundError
from ..util.logging import LoggerMixin
from .models import ConversationRead
from .repository import ConversationRepository


class ConversationService(LoggerMixin):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.repository = ConversationRepository(session)
        self._log_info("ConversationService initialized")

    async def create_new_conversation(self) -> ConversationRead:
        """Create a new conversation with comprehensive logging."""
        with self._log_operation("create_new_conversation"):
            self._log_info("Creating new conversation")
            
            conversation = await self.repository.create_conversation()
            conversation_data = ConversationRead.model_validate(conversation)
            
            self._log_info(
                "New conversation created successfully",
                conversation_id=conversation_data.id,
                created_at=conversation_data.created_at.isoformat()
            )
            
            return conversation_data

    async def get_all_conversations(self) -> list[ConversationRead]:
        """Retrieve all conversations with logging."""
        with self._log_operation("get_all_conversations"):
            self._log_info("Retrieving all conversations")
            
            conversations = await self.repository.get_all_conversations()
            conversation_data = [ConversationRead.model_validate(conv) for conv in conversations]
            
            self._log_info(
                "Retrieved conversations successfully",
                conversation_count=len(conversation_data)
            )
            
            return conversation_data

    async def get_conversation_by_id(self, conversation_id: int) -> ConversationRead:
        """Retrieve a specific conversation by ID with detailed logging."""
        with self._log_operation("get_conversation_by_id", conversation_id=conversation_id):
            self._log_info(
                "Retrieving conversation by ID", 
                conversation_id=conversation_id
            )
            
            conversation = await self.repository.get_conversation_by_id(conversation_id)
            
            if not conversation:
                self._log_warning(
                    "Conversation not found",
                    conversation_id=conversation_id
                )
                raise NotFoundError("Conversation", conversation_id)
            
            conversation_data = ConversationRead.model_validate(conversation)
            
            self._log_info(
                "Conversation retrieved successfully",
                conversation_id=conversation_data.id,
                created_at=conversation_data.created_at.isoformat()
            )
            
            return conversation_data 