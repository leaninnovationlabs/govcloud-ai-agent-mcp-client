from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database.session import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )


class ConversationCreate(BaseModel):
    pass


class ConversationRead(BaseModel):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True} 