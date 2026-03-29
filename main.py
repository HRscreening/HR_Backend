import configs.env_config
from fastapi import FastAPI,Depends
# from configs.db import init_db
from src.routes.auth_routes import router as auth_router
from src.routes.user_routes import router as user_router
from src.routes.job_routes import router as job_router
from src.routes.batch_routes import router as batch_router
from src.routes.application_routes import router as application_router
from src.routes.candidate_routes import router as candidate_router
from src.routes.org_routes import router as org_router


from src.modules.interviews.routes.interview_round_config_route import router as interview_round_config_router
from src.modules.interviews.routes.interview_routes import router as interview_router
from src.modules.interviews.routes.panlist_route import unproducted_router as panelist_unprotected_router
from src.modules.interviews.routes.candidate_booking_route import unprotected_router as candidate_booking_router

from src.modules.oauth.oauth_routes import router as oauth_router
from src.routes.jd_routes import router as jd_router
from src.routes.form_config_routes import router as form_config_router
from src.routes.jd_builder_routes import router as jd_builder_router
from src.routes.public_apply_routes import unprotected_router as public_apply_router

from fastapi.middleware.cors import CORSMiddleware
from src.middlewares.verify_user import auth_required 


import logging
from exception_handlers import domain_exception_handler, validation_exception_handler
from fastapi.exceptions import RequestValidationError
from src.services.errors.base import DomainError
from configs.supabase_config import supabase
import src.models
from configs.env_config import LANGHAIN_TRACKING_ENABLED, LANGCHAIN_API_KEY,ENVIRONMENT,REDIS_HOST

app = FastAPI()

LANGHAIN_TRACKING_ENABLED 
LANGCHAIN_API_KEY

print("ENV:", ENVIRONMENT)
print("REDIS_HOST:", REDIS_HOST)

# Configure logging
logging.basicConfig(level=logging.INFO)


app.add_exception_handler(DomainError, domain_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://localhost:5174","https://m7wgw6b2-5173.inc1.devtunnels.ms"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/")
async def root():
    return {"message": "Hello World",}


app.include_router(auth_router)
app.include_router(user_router,dependencies=[Depends(auth_required)])
app.include_router(job_router,dependencies=[Depends(auth_required)])
app.include_router(batch_router,dependencies=[Depends(auth_required)])
app.include_router(application_router,dependencies=[Depends(auth_required)])
app.include_router(candidate_router,dependencies=[Depends(auth_required)])
app.include_router(org_router,dependencies=[Depends(auth_required)])
# Interview routes
app.include_router(interview_round_config_router,dependencies=[Depends(auth_required)])
app.include_router(interview_router,dependencies=[Depends(auth_required)])

app.include_router(panelist_unprotected_router)
app.include_router(candidate_booking_router)
app.include_router(oauth_router)
# JD Builder & Public Apply
app.include_router(jd_router, dependencies=[Depends(auth_required)])
app.include_router(form_config_router, dependencies=[Depends(auth_required)])
app.include_router(jd_builder_router, dependencies=[Depends(auth_required)])
app.include_router(public_apply_router)  # unprotected — candidate-facing
