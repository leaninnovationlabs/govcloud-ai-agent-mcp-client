from datetime import datetime
from enum import Enum

from pydantic import BaseModel
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database.session import Base


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id"), nullable=False
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )


class MessageCreate(BaseModel):
    content: str
    conversation_id: int


class MessageRead(BaseModel):
    id: int
    content: str
    role: MessageRole
    timestamp: datetime
    conversation_id: int

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    message: str  # Frontend sends "message", not "content"
    conversation_id: int


class ChatResponse(BaseModel):
    content: str 