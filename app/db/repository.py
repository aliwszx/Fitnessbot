from typing import Optional
from supabase import AsyncClient
from app.db.models import UserCreate, User, MessageCreate, Message, WorkoutCreate, Workout
from app.core.logging import get_logger

logger = get_logger(__name__)


class UserRepository:
    def __init__(self, db: AsyncClient):
        self.db = db

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        try:
            result = (
                await self.db.table("users")
                .select("*")
                .eq("telegram_id", telegram_id)
                .maybe_single()
                .execute()
            )
            return User(**result.data) if result.data else None
        except Exception as e:
            logger.error(f"Error fetching user {telegram_id}: {e}")
            return None

    async def create(self, user_data: UserCreate) -> Optional[User]:
        try:
            result = (
                await self.db.table("users")
                .insert(user_data.model_dump())
                .execute()
            )
            return User(**result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None

    async def get_or_create(self, user_data: UserCreate) -> Optional[User]:
        user = await self.get_by_telegram_id(user_data.telegram_id)
        if user:
            return user
        return await self.create(user_data)

    async def increment_message_count(self, telegram_id: int) -> None:
        try:
            await (
                self.db.rpc(
                    "increment_message_count",
                    {"p_telegram_id": telegram_id},
                ).execute()
            )
        except Exception as e:
            logger.error(f"Error incrementing message count: {e}")


class MessageRepository:
    def __init__(self, db: AsyncClient):
        self.db = db

    async def save(self, message: MessageCreate) -> Optional[Message]:
        try:
            result = (
                await self.db.table("messages")
                .insert(message.model_dump())
                .execute()
            )
            return Message(**result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            return None

    async def get_history(
        self,
        telegram_id: int,
        session_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[Message]:
        try:
            query = (
                self.db.table("messages")
                .select("*")
                .eq("telegram_id", telegram_id)
                .order("created_at", desc=False)
                .limit(limit)
            )
            if session_id:
                query = query.eq("session_id", session_id)

            result = await query.execute()
            return [Message(**row) for row in result.data]
        except Exception as e:
            logger.error(f"Error fetching history: {e}")
            return []

    async def clear_history(self, telegram_id: int) -> None:
        try:
            await (
                self.db.table("messages")
                .delete()
                .eq("telegram_id", telegram_id)
                .execute()
            )
        except Exception as e:
            logger.error(f"Error clearing history: {e}")


class WorkoutRepository:
    def __init__(self, db: AsyncClient):
        self.db = db

    async def create(self, workout: WorkoutCreate) -> Optional[Workout]:
        """Yeni workout-u (adətən status='draft' ilə) Supabase-də yaradır."""
        try:
            result = (
                await self.db.table("workouts")
                .insert(workout.model_dump())
                .execute()
            )
            return Workout(**result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Error creating workout: {e}")
            return None

    async def update_program(
        self, workout_id: int, program: str, edit_type: str
    ) -> Optional[Workout]:
        """Mövcud workout-un mətnini yeniləyir (manual və ya AI redaktəsi)."""
        try:
            result = (
                await self.db.table("workouts")
                .update({"program": program, "last_edit_type": edit_type})
                .eq("id", workout_id)
                .execute()
            )
            return Workout(**result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Error updating workout {workout_id}: {e}")
            return None

    async def accept(self, workout_id: int) -> Optional[Workout]:
        """Workout-u 'accepted' statusuna keçirir — istifadəçi yekun versiyanı qəbul edib."""
        try:
            result = (
                await self.db.table("workouts")
                .update({"status": "accepted"})
                .eq("id", workout_id)
                .execute()
            )
            return Workout(**result.data[0]) if result.data else None
        except Exception as e:
            logger.error(f"Error accepting workout {workout_id}: {e}")
            return None

    async def get_by_id(self, workout_id: int) -> Optional[Workout]:
        try:
            result = (
                await self.db.table("workouts")
                .select("*")
                .eq("id", workout_id)
                .maybe_single()
                .execute()
            )
            return Workout(**result.data) if result.data else None
        except Exception as e:
            logger.error(f"Error fetching workout {workout_id}: {e}")
            return None

    async def get_latest_accepted(self, telegram_id: int) -> Optional[Workout]:
        try:
            result = (
                await self.db.table("workouts")
                .select("*")
                .eq("telegram_id", telegram_id)
                .eq("status", "accepted")
                .order("updated_at", desc=True)
                .limit(1)
                .maybe_single()
                .execute()
            )
            return Workout(**result.data) if result.data else None
        except Exception as e:
            logger.error(f"Error fetching latest workout for {telegram_id}: {e}")
            return None
