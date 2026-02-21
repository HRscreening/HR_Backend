from fastapi import UploadFile
from typing import List
from configs.supabase_config import supabase
from src.models import job_model
import os
import mimetypes
from pathlib import Path
from configs.supabase_config import SUPABASE_URL
import asyncio
from supabase import StorageException
from storage3.exceptions import StorageException
from configs.log_config import get_logger

# class SupabaseFileHandler:
#     def __init__(self):
#         self.AllowedMIMETypes = ["application/pdf"]
#         self.allowed_buckets_name = ["resumes"]
    
   
#     def get_public_url(self,full_path:str):
#          return f"{SUPABASE_URL}/storage/v1/object/public/{full_path}"
     
   
#     def get_signed_url(self,bucket, path, expires=3600):
#         return supabase.storage.from_(bucket).create_signed_url(
#             path,
#             expires
#         ).data["signedUrl"]

    
   
#     def validate_bucket_name(self, bucket_name: str) -> bool:
#         """Validates if the provided bucket name is allowed."""
#         return bucket_name in self.allowed_buckets_name
    
   
#     async def create_bucket(self, bucket_name: str) -> None:
#         """Creates a new Supabase storage bucket."""
#         response = supabase.storage.create_bucket(bucket_name,options={
#             "public": True,
#             # "allowed_mime_types": ["image/png"],
#             # "file_size_limit": 1024,
#         })
#         if response.get("error"):
#             raise Exception(f"Error creating bucket: {response['error']['message']}")
        
   
#     async def delete_bucket(self, bucket_name: str) -> None:
#         """Deletes a Supabase storage bucket."""
        
#         if not self.validate_bucket_name(bucket_name):
#             raise Exception(f"Bucket name '{bucket_name}' is not allowed to be deleted.")
        
#         response = supabase.storage.delete_bucket(bucket_name)
#         if response.get("error"):
#             raise Exception(f"Error deleting bucket: {response['error']['message']}")
        
   
#     async def empty_bucket(self, bucket_name: str) -> None:
#         """Empties all files from a Supabase storage bucket."""
        
#         if not self.validate_bucket_name(bucket_name):
#             raise Exception(f"Bucket name '{bucket_name}' is not allowed to be emptied.")
        
#         response = supabase.storage.empty_bucket(bucket_name)
#         if response.get("error"):
#             raise Exception(f"Error emptying bucket: {response['error']['message']}")
           
        
   
#     async def save_file(self, file: UploadFile, bucket_name:str,destination_path: str) -> str:
#         """Saves an uploaded file to the specified destination path"""
        
#         if not self.validate_bucket_name(bucket_name):
#             raise Exception(f"Bucket name '{bucket_name}' is not allowed.")
        
#         if not file.filename:
#             raise Exception("File name is empty.")

#         response = (
#             supabase.storage
#             .from_(bucket_name)
#             .upload(
#                 path=f"{destination_path}/{file.filename}",
#                 file=file.file, 
#                 file_options={
#                     "cache-control": "3600",
#                     "upsert": False,
#                     "content-type": file.content_type,
#                 },
#             )
#         )

#         if response.get("error"):
#             raise Exception(
#                 f"Error uploading file: {response['error']['message']}"
#             )

   
#     def save_file_from_path(
#         self,
#         local_file_path: str,
#         bucket_name: str,
#         destination_path: str,
#     ) -> str:
#         """
#         Uploads a file to Supabase Storage.

#         Args:
#             local_file_path (str): Local file path on disk
#             bucket_name (str): Supabase bucket name
#             destination_path (str): Path inside bucket (including filename)

#         Returns:
#             str: Full storage path (bucket/path/to/file)
#         """

#         file_path = Path(local_file_path)

#         with file_path.open("rb") as f:
#             response = supabase.storage.from_(bucket_name).upload(
#                 destination_path,
#                 f,
#                 file_options={"content-type": "application/pdf"},
#             )

#         if response.error:
#             raise Exception(response.error.message)

#         return f"{bucket_name}/{destination_path}"
    
    
#     def save_file_from_path(
#             local_file_path: str,
#             bucket_name: str,
#             destination_path: str,
#         ) -> str:

#             """
#             Uploads a file to Supabase Storage.

#             Args:
#                 local_file_path (str): Local file path on disk
#                 bucket_name (str): Supabase bucket name
#                 destination_path (str): Path inside bucket (including filename)

#             Returns:
#                 str: Full storage path (bucket/path/to/file)
#             """

#             file_path = Path(local_file_path)
            
#             try:

#                 with file_path.open("rb") as f:
#                     response = supabase.storage.from_(bucket_name).upload(
#                         destination_path,
#                         f,
#                         file_options={"content-type": "application/pdf"},
#                     )

#             except StorageException as e:
#                 if "409" in str(e) or "Duplicate" in str(e):
#                     # File already exists → skip
#                     return f"{bucket_name}/{destination_path}"
                
#                 if hasattr(response, "error") and response.error:
#                     raise Exception(response.error.message)
                



   
#     async def save_files(
#     self,
#     files: List[str],      
#     bucket_name: str,
#     destination_path: str,):
#         """Uploads files from disk to Supabase storage."""

#         if not files:
#             raise Exception("No files provided for upload.")

#         if not self.validate_bucket_name(bucket_name):
#             raise Exception(f"Bucket name '{bucket_name}' is not allowed.")

#         for file_path in files:
#             if not os.path.exists(file_path):
#                 raise Exception(f"File does not exist: {file_path}")

#             file_name = os.path.basename(file_path)

#             content_type, _ = mimetypes.guess_type(file_name)
#             content_type = content_type or "application/octet-stream"

#             with open(file_path, "rb") as f:
#                 response = (
#                     supabase.storage
#                     .from_(bucket_name)
#                     .upload(
#                         path=f"{destination_path}/{file_name}",
#                         file=f,
#                         file_options={
#                             "cache-control": "3600",
#                             "upsert": False,
#                             "content-type": content_type,
#                         },
#                     )
#                 )

#                 print(response)
#             if hasattr(response, "get") and response.get("error"):
#                 raise Exception(
#                     f"Error uploading {file_name}: {response['error']['message']}"
#                 )
                
                            
   
#     async def move_file(self, bucket_name: str, source_path: str, destination_path: str) -> None:
#         """Moves a file within a Supabase storage bucket."""
        
#         if not self.validate_bucket_name(bucket_name):
#             raise Exception(f"Bucket name '{bucket_name}' is not allowed.")
        
#         response = supabase.storage.from_(bucket_name).move(source_path, destination_path)
        
#         if response.get("error"):
#             raise Exception(f"Error moving file: {response['error']['message']}")


from fastapi import UploadFile
from typing import List
from pathlib import Path
import os
import mimetypes

from configs.supabase_config import supabase, SUPABASE_URL
from storage3.exceptions import StorageException


class SupabaseFileHandler:

    def __init__(self):
        self.allowed_buckets = {"resumes"}
        self.allowed_mime_types = {"application/pdf"}
        self.logger = get_logger("SUPABASE_FILE_HANDLER")

    # ------------------ Utils ------------------

    def validate_bucket(self, bucket: str):
        if bucket not in self.allowed_buckets:
            raise ValueError(f"Bucket '{bucket}' not allowed")

    def get_public_url(self, full_path: str) -> str:
        return f"{SUPABASE_URL}/storage/v1/object/public/{full_path}"

    # ------------------ Upload from UploadFile ------------------

    async def save_file(
        self,
        file: UploadFile,
        bucket: str,
        destination_path: str,
    ) -> str:

        self.validate_bucket(bucket)

        if not file.filename:
            raise ValueError("Empty filename")

        if file.content_type not in self.allowed_mime_types:
            raise ValueError("Unsupported file type")

        storage_path = f"{destination_path}/{file.filename}"

        response = supabase.storage.from_(bucket).upload(
            storage_path,
            file.file,
            file_options={
                "cache-control": "3600",
                "upsert": False,
                "content-type": file.content_type,
            },
        )

        if getattr(response, "error", None):
            raise Exception(response.error.message)

        return f"{bucket}/{storage_path}"

    # ------------------ Upload from disk ------------------

    def save_file_from_path(
        self,
        local_path: str,
        bucket: str,
        destination_path: str,
    ) -> str:

        self.validate_bucket(bucket)

        file_path = Path(local_path)

        if not file_path.exists():
            raise FileNotFoundError(local_path)

        try:
            with file_path.open("rb") as f:
                response = supabase.storage.from_(bucket).upload(
                    destination_path,
                    f,
                    file_options={"content-type": "application/pdf"},
                )

        except StorageException as e:
            self.logger.info(f"StorageException during upload: {e}")
            # Duplicate file → ignore
            if "409" in str(e) or "Duplicate" in str(e):
                return f"{bucket}/{destination_path}"
            raise

        if getattr(response, "error", None):
            raise Exception(response.error.message)

        return f"{bucket}/{destination_path}"

    # ------------------ Bulk upload from disk ------------------

    def save_files(
        self,
        files: List[str],
        bucket: str,
        destination_path: str,
    ):

        self.validate_bucket(bucket)

        if not files:
            raise ValueError("No files provided")

        for path in files:

            if not os.path.exists(path):
                raise FileNotFoundError(path)

            file_name = os.path.basename(path)

            content_type, _ = mimetypes.guess_type(file_name)
            content_type = content_type or "application/octet-stream"

            with open(path, "rb") as f:
                response = supabase.storage.from_(bucket).upload(
                    f"{destination_path}/{file_name}",
                    f,
                    file_options={
                        "cache-control": "3600",
                        "upsert": False,
                        "content-type": content_type,
                    },
                )

            if getattr(response, "error", None):
                raise Exception(response.error.message)



supbase_file_manager = SupabaseFileHandler()

def save_file_from_path(
        local_file_path: str,
        bucket_name: str,
        destination_path: str,
    ) -> str:

        """
        Uploads a file to Supabase Storage.

        Args:
            local_file_path (str): Local file path on disk
            bucket_name (str): Supabase bucket name
            destination_path (str): Path inside bucket (including filename)

        Returns:
            str: Full storage path (bucket/path/to/file)
        """

        file_path = Path(local_file_path)
        
        try:

            with file_path.open("rb") as f:
                response = supabase.storage.from_(bucket_name).upload(
                    destination_path,
                    f,
                    file_options={"content-type": "application/pdf"},
                )

        except StorageException as e:
           if "409" in str(e) or "Duplicate" in str(e):
            # File already exists → skip
            return f"{bucket_name}/{destination_path}"
        
        if hasattr(response, "error") and response.error:
            raise Exception(response.error.message)
        

