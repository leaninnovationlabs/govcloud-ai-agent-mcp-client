from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..util.logging import LoggerMixin
from .models import Message, MessageCreate, MessageRole


class MessageRepository(LoggerMixin):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.session = session
        self._log_debug("MessageRepository initialized")

    async def create_message(
        self, content: str, role: MessageRole, conversation_id: int
    ) -> Message:
        """Create a new message with detailed database logging."""
        with self._log_operation(
            "db_create_message", 
            role=role.value, 
            conversation_id=conversation_id
        ):
            self._log_info(
                "Creating new message in database",
                role=role.value,
                conversation_id=conversation_id,
                content_length=len(content),
                content_preview=content[:100] + "..." if len(content) > 100 else content
            )
            
            try:
                message = Message(
                    content=content,
                    role=role.value,
                    conversation_id=conversation_id,
                )
                self.session.add(message)
                
                self._log_debug(
                    "Message entity created, committing to database",
                    role=role.value,
                    conversation_id=conversation_id
                )
                await self.session.commit()
                
                self._log_debug("Database commit successful, refreshing entity")
                await self.session.refresh(message)
                
                self._log_info(
                    "Message created successfully in database",
                    message_id=message.id,
                    role=role.value,
                    conversation_id=conversation_id,
                    timestamp=message.timestamp.isoformat(),
                    content_length=len(content)
                )
                
                return message
                
            except Exception as e:
                self._log_error(
                    "Failed to create message in database",
                    exc_info=e,
                    role=role.value,
                    conversation_id=conversation_id,
                    content_length=len(content),
                    error_type=type(e).__name__
                )
                await self.session.rollback()
                raise

    async def get_messages_by_conversation_id(
        self, conversation_id: int
    ) -> list[Message]:
        """Retrieve messages for a conversation with performance logging."""
        with self._log_operation("db_get_messages_by_conversation", conversation_id=conversation_id):
            self._log_info(
                "Querying messages by conversation ID from database",
                conversation_id=conversation_id
            )
            
            try:
                result = await self.session.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.timestamp.asc())
                )
                messages = list(result.scalars().all())
                
                # Calculate message statistics for logging
                user_messages = [m for m in messages if m.role == MessageRole.USER.value]
                assistant_messages = [m for m in messages if m.role == MessageRole.ASSISTANT.value]
                
                self._log_info(
                    "Successfully retrieved messages from database",
                    conversation_id=conversation_id,
                    total_messages=len(messages),
                    user_messages=len(user_messages),
                    assistant_messages=len(assistant_messages)
                )
                
                return messages
                
            except Exception as e:
                self._log_error(
                    "Failed to retrieve messages from database",
                    exc_info=e,
                    conversation_id=conversation_id,
                    error_type=type(e).__name__
                )
                raise 