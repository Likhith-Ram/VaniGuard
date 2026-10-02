from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from api.core.database import get_db
from api.repositories.user_repository import UserRepository
from api.schemas import (
    UserCreate,
    UserRead,
    TrustedContactCreate,
    TrustedContactRead,
)
from api.security import require_api_key

# All routes in this router require API-key authentication.
router = APIRouter(
    prefix="/api/users",
    tags=["users"],
    dependencies=[Depends(require_api_key)],
)


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    existing = await repo.get_user_by_phone(user.phone_number)
    if existing:
        raise HTTPException(status_code=400, detail="User with this phone number already exists")
    new_user = await repo.create_user(phone_number=user.phone_number, full_name=user.full_name)
    return new_user


@router.get("/", response_model=List[UserRead])
async def get_users(limit: int = 20, offset: int = 0, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    users = await repo.get_all_users(limit=limit, offset=offset)
    return users


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    user = await repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    deleted = await repo.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")


# ── Trusted Contacts ──────────────────────────────────────────────────────────

@router.post("/{user_id}/contacts", response_model=TrustedContactRead, status_code=status.HTTP_201_CREATED)
async def add_trusted_contact(user_id: UUID, contact: TrustedContactCreate, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    new_contact = await repo.add_trusted_contact(
        user_id=user_id,
        contact_name=contact.contact_name,
        contact_phone=contact.contact_phone,
        relationship_type=contact.relationship_type,
    )
    if not new_contact:
        raise HTTPException(status_code=404, detail="User not found")
    return new_contact


@router.get("/{user_id}/contacts", response_model=List[TrustedContactRead])
async def get_trusted_contacts(user_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    user = await repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    contacts = await repo.get_trusted_contacts(user_id)
    return contacts


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trusted_contact(contact_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    deleted = await repo.delete_trusted_contact(contact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Contact not found")
