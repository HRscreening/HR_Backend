from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from utils.jwt import decode_jwt
from configs.postgress_db import get_db
from models.user_model import User


async def auth_required(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid token",
        )

    token = auth_header.split(" ", 1)[1]
    payload = decode_jwt(token)

    if not payload or "user_id" not in payload:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token invalid or expired",
        )
        
    try:
        user_id = UUID(payload["user_id"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user ID in token",
        )

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    request.state.user = user
    return user
