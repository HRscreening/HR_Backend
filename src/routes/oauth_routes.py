
from fastapi import APIRouter,HTTPException,Depends,Request,status,Query
from fastapi.responses import RedirectResponse
from  typing import Optional,List
from uuid import UUID
from src.dependency import get_candidate_service,CandidateService
from src.models.enums import ApplicationStatus
from src.schemas.candidate_schemas import CandidateCreateSchema,CandidateUpdateSchema
from src.middlewares.verify_user import auth_required 
from src.dependency import get_oauth_service,OAuthService,get_jwt_service,get_panelist_repository,PanelistRepository
from src.utils.jwt import JWTService
from configs.env_config import FRONTEND_URL

router = APIRouter(prefix="/api/oauth", tags=["OAuth Integration"])




@router.get("/google/calendar")
async def connect_google_calendar(
    request: Request,
    _ : None = Depends(auth_required),
    redirect_to: str = Query(..., description="Frontend URL to redirect after successful connection"),
    jwt_service: JWTService = Depends(get_jwt_service),
    oauth_service: OAuthService = Depends(get_oauth_service),
):

    user_id = request.state.user.id
    
    print("User ID for OAuth connection:", user_id)
    print("Redirect URL:", redirect_to)

    state_payload = {
        "type": "user",
        "user_id": str(user_id),
        "redirect_to": redirect_to
    }
    
    
    print("State Payload:", state_payload)

    state = jwt_service.encode_oauth_state(state_payload)

    url = oauth_service.get_google_calendar_auth_url(state)
    
    print("Redirecting to:", url)

    return url




@router.get("/google/calendar/panelist",status_code=status.HTTP_302_FOUND)
async def connect_panelist_calendar(
    token: str = Query(..., description="Panelist invite token"),
    redirect_to: str = Query(..., description="Frontend URL to redirect after successful connection"),
    jwt_service : JWTService = Depends(get_jwt_service),
    oauth_service: OAuthService = Depends(get_oauth_service),
):

    state_payload = {
        "type": "panelist",
        "invite_token": token,
        "redirect_to": redirect_to
    }

    state = jwt_service.encode_oauth_state(state_payload)

    url = oauth_service.get_google_calendar_auth_url(state)
    
    print("Redirecting to:", url)

    return url



@router.get("/google/calendar/callback")
async def google_calendar_callback(
    code: str,
    state: str,
    jwt_service : JWTService = Depends(get_jwt_service),
    panelist_repo : PanelistRepository = Depends(get_panelist_repository),
    oauth_service: OAuthService = Depends(get_oauth_service),
):

    payload = jwt_service.decode_oauth_state(state)

    if payload["type"] == "user":

        await oauth_service.handle_google_calendar_callback(
            code=code,
            user_id=payload["user_id"]
        )

    elif payload["type"] == "panelist":

        invite_token = payload["invite_token"]

        panelist = await panelist_repo.get_by_invite_token(invite_token)

        await oauth_service.handle_google_calendar_callback(
            code=code,
            user_email=panelist.email,
            user_id=None
        )

    return RedirectResponse(f"{FRONTEND_URL}{payload['redirect_to']}")