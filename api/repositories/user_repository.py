from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from api.models.models import User, TrustedContact

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, phone_number: str, full_name: Optional[str] = None) -> User:
        user = User(phone_number=phone_number, full_name=full_name)
        self.db.add(user)
        await self.db.flush()
        return user

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        result = await self.db.execute(
            select(User).options(selectinload(User.contacts)).where(User.id == user_id)
        )
        return result.scalars().first()

    async def get_user_by_phone(self, phone_number: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).options(selectinload(User.contacts)).where(User.phone_number == phone_number)
        )
        return result.scalars().first()
    
    async def get_all_users(self, limit: int = 20, offset: int = 0) -> List[User]:
        result = await self.db.execute(
            select(User).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def delete_user(self, user_id: UUID) -> bool:
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        await self.db.delete(user)
        await self.db.flush()
        return True

    # Trusted Contacts
    async def add_trusted_contact(self, user_id: UUID, contact_name: str, contact_phone: str, relationship_type: Optional[str] = None) -> Optional[TrustedContact]:
        user = await self.get_user_by_id(user_id)
        if not user:
            return None
            
        contact = TrustedContact(
            user_id=user_id,
            contact_name=contact_name,
            contact_phone=contact_phone,
            relationship_type=relationship_type
        )
        self.db.add(contact)
        await self.db.flush()
        return contact

    async def get_trusted_contacts(self, user_id: UUID) -> List[TrustedContact]:
        result = await self.db.execute(
            select(TrustedContact).where(TrustedContact.user_id == user_id)
        )
        return list(result.scalars().all())

    async def delete_trusted_contact(self, contact_id: UUID) -> bool:
        result = await self.db.execute(
            select(TrustedContact).where(TrustedContact.id == contact_id)
        )
        contact = result.scalars().first()
        if not contact:
            return False
        await self.db.delete(contact)
        await self.db.flush()
        return True
