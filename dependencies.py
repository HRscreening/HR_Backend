# # app/dependencies.py
# from fastapi import Depends
# from configs.postgress_db import get_db
# # from repositories.job_repo import JobRepository
# from services.job_service import JobService



# def get_job_repository(db=Depends(get_db)):
#     return JobRepository(db)

# def get_job_service(
#     job_repo=Depends(get_job_repository),
# ):
#     return JobService(job_repo)
