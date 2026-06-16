from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class UserCreate(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: Optional[str] = None


class User(UserCreate):
    id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    message_count: int = 0


class MessageCreate(BaseModel):
    user_id: int
    telegram_id: int
    role: str  # "user" | "assistant"
    content: str
    session_id: Optional[str] = None


class Message(MessageCreate):
    id: int
    created_at: datetime


class ConversationSession(BaseModel):
    session_id: str
    telegram_id: int
    messages: list[MessageCreate] = Field(default_factory=list)


class WorkoutCreate(BaseModel):
    user_id: int
    telegram_id: int
    program: str
    days: Optional[str] = None
    goal: Optional[str] = None
    level: Optional[str] = None
    equipment: Optional[str] = None
    muscles: Optional[str] = None
    status: str = "draft"  # "draft" | "accepted"


class Workout(WorkoutCreate):
    id: int
    last_edit_type: Optional[str] = None  # "manual" | "ai"
    created_at: datetime
    updated_at: datetime
