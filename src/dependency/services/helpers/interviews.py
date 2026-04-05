from fastapi import Depends
from src.dependency.services.helpers.helper_services import get_jwt_service 
from src.modules.interviews.services.helpers.token_manager.base import BaseTokenManager
from src.modules.interviews.services.helpers.token_manager.Interview_token_manger import InterviewTokenManagerFactory

def get_interview_token_manager_factory():
    jwt_service = get_jwt_service()
    return InterviewTokenManagerFactory(jwt_service)