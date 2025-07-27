from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..util.logging import LoggerMixin
from .models import Conversation, ConversationCreate


class ConversationRepository(LoggerMixin):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.session = session
        self._log_debug("ConversationRepository initialized")

    async def create_conversation(self) -> Conversation:
        """Create a new conversation with detailed database logging."""
        with self._log_operation("db_create_conversation"):
            self._log_info("Creating new conversation in database")
            
            try:
                conversation = Conversation()
                self.session.add(conversation)
                
                self._log_debug("Conversation entity created, committing to database")
                await self.session.commit()
                
                self._log_debug("Database commit successful, refreshing entity")
                await self.session.refresh(conversation)
                
                self._log_info(
                    "Conversation created successfully in database",
                    conversation_id=conversation.id,
                    created_at=conversation.created_at.isoformat()
                )
                
                return conversation
                
            except Exception as e:
                self._log_error(
                    "Failed to create conversation in database",
                    exc_info=e,
                    error_type=type(e).__name__
                )
                await self.session.rollback()
                raise

    async def get_all_conversations(self) -> list[Conversation]:
        """Retrieve all conversations with database performance logging."""
        with self._log_operation("db_get_all_conversations"):
            self._log_info("Querying all conversations from database")
            
            try:
                result = await self.session.execute(
                    select(Conversation).order_by(Conversation.created_at.desc())
                )
                conversations = list(result.scalars().all())
                
                self._log_info(
                    "Successfully retrieved conversations from database",
                    conversation_count=len(conversations)
                )
                
                return conversations
                
            except Exception as e:
                self._log_error(
                    "Failed to retrieve conversations from database",
                    exc_info=e,
                    error_type=type(e).__name__
                )
                raise

    async def get_conversation_by_id(self, conversation_id: int) -> Conversation | None:
        """Retrieve a specific conversation with detailed logging."""
        with self._log_operation("db_get_conversation_by_id", conversation_id=conversation_id):
            self._log_info(
                "Querying conversation by ID from database",
                conversation_id=conversation_id
            )
            
            try:
                result = await self.session.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
                conversation = result.scalar_one_or_none()
                
                if conversation:
                    self._log_info(
                        "Conversation found in database",
                        conversation_id=conversation_id,
                        created_at=conversation.created_at.isoformat()
                    )
                else:
                    self._log_info(
                        "Conversation not found in database",
                        conversation_id=conversation_id
                    )
                
                return conversation
                
            except Exception as e:
                self._log_error(
                    "Failed to retrieve conversation from database",
                    exc_info=e,
                    conversation_id=conversation_id,
                    error_type=type(e).__name__
                )
                raise 