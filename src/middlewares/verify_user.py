
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from sqlalchemy import select
from src.schemas.request_context_schema import RequestContext
# from src.utils.jwt import decode_jwt
from configs.postgress_db import get_db
from src.models.user_model import User
from src.dependency import get_jwt_service
from src.utils.jwt import JWTService




async def auth_required(
    request: Request,
    jwt:JWTService = Depends(get_jwt_service),
    db: AsyncSession = Depends(get_db),
):
    # ---------- AUTH ----------
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid token",
        )

    token = auth_header.split(" ", 1)[1]
    payload = jwt.decode_token(token)

    if not payload or "user_id" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalid or expired",
        )

    try:
        user_id = UUID(payload["user_id"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
        )

    # TODO: Need to remove this db call
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

    # ---------- CONTEXT ----------
    context_type = request.headers.get("X-Context-Type", "personal")
    context_org_id = request.headers.get("X-Context-Id")

    if context_type == "personal":
        request.state.context = RequestContext(type="personal")
        return user

    if context_type != "org":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid context type",
        )

    if not context_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing org context id",
        )

    try:
        org_id = UUID(context_org_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid org id",
        )

    # ---------- ORG MEMBERSHIP VALIDATION ----------
    # TODO: Need to remove this db call
    result = await db.execute(
        select(User)
        .where(
            User.id == user_id,
            User.organization_id == org_id,
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not part of this organization",
        )

    request.state.context = RequestContext(
        type="org",
        org_id=org_id,
        role=membership.role,
    )

    print("Request context :", request.state.context.__dict__)
    return user
