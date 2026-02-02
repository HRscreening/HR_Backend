import os
import shutil
from typing import List
from fastapi import UploadFile
from configs.env_config import BASE_UPLOAD_DIR

ALLOWED_EXTENSIONS = {"pdf", "docx"}



class FileService:

    @classmethod
    async def stage_uploaded_files(
        cls,
        job_id: str,
        files: List[UploadFile],
    ) -> list[str]:
        """
        Streams uploaded files to disk for later background processing.
        Returns list of saved file paths.
        """

        job_dir = os.path.join(BASE_UPLOAD_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)

        saved_paths: list[str] = []

        for file in files:
            if not file.filename:
                raise ValueError("File name is empty")

            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise ValueError(f"Unsupported file type: {file.filename}")

            dest_path = os.path.join(job_dir, file.filename)
            
            
            with open(dest_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            saved_paths.append(dest_path)

        return saved_paths
