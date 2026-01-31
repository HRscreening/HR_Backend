from fastapi import FastAPI,Depends
# from configs.db import init_db
from routes.auth_routes import router as auth_router
from routes.user_routes import router as user_router
from routes.job_routes import router as job_router
from fastapi.middleware.cors import CORSMiddleware
from middlewares.verify_user import auth_required 


import logging
from exception_handlers import domain_exception_handler
from services.errors.base import DomainError
import models
from configs.env_config import LANGHAIN_TRACKING_ENABLED, LANGCHAIN_API_KEY

app = FastAPI()


# Configure logging
logging.basicConfig(level=logging.INFO)


app.add_exception_handler(DomainError, domain_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://localhost:5174"],  # Replace "*" with your frontend URL for better security
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

