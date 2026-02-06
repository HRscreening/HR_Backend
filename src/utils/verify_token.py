from fastapi import  Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from bson import ObjectId
from src.utils.jwt import decode_jwt
from configs.postgress_db import get_db  


async def verify_token(token: str, db: AsyncSession = Depends(get_db)):
   
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    payload = decode_jwt(token)

    if not payload or "user_id" not in payload:
        raise HTTPException(status_code=403, detail="Token invalid or expired")

    user = await db["users"].find_one({"_id": ObjectId(payload["user_id"])})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # print(f"Authenticated user: {user}")
    
    return user

