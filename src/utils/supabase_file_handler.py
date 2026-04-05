from fastapi import UploadFile
from typing import List
from configs.supabase_config import supabase
import os
import json
import mimetypes
import tempfile
from pathlib import Path
from configs.supabase_config import SUPABASE_URL
from supabase import StorageException
from storage3.exceptions import StorageException
from src.utils.file_manager import FileManagerService,fileManager

class SupabaseFileHandler:
    def __init__(self):
        self.file_manager = FileManagerService()
        
    AllowedMIMETypes = ["application/pdf"]
    allowed_buckets_name = ["resumes"]
    
    
    def get_public_url(self, full_path: str):
         return f"{SUPABASE_URL}/storage/v1/object/public/{full_path}"
     
    
    def get_signed_url(self, bucket, path, expires=3600):
        return supabase.storage.from_(bucket).create_signed_url(
            path,
            expires
        ).data["signedUrl"]

    
    
    def validate_bucket_name(self, bucket_name: str) -> bool:
        """Validates if the provided bucket name is allowed."""
        return bucket_name in ["resumes", "transcripts"]
    
    
    async def create_bucket(self, bucket_name: str) -> None:
        """Creates a new Supabase storage bucket."""
        response = supabase.storage.create_bucket(bucket_name,options={
            "public": True,
            # "allowed_mime_types": ["image/png"],
            # "file_size_limit": 1024,
        })
        if response.get("error"):
            raise Exception(f"Error creating bucket: {response['error']['message']}")
        
    
    async def delete_bucket(self, bucket_name: str) -> None:
        """Deletes a Supabase storage bucket."""
        
        if not self.validate_bucket_name(bucket_name):
            raise Exception(f"Bucket name '{bucket_name}' is not allowed to be deleted.")
        
        response = supabase.storage.delete_bucket(bucket_name)
        if response.get("error"):
            raise Exception(f"Error deleting bucket: {response['error']['message']}")
        
    
    async def empty_bucket(self, bucket_name: str) -> None:
        """Empties all files from a Supabase storage bucket."""
        
        if not self.validate_bucket_name(bucket_name):
            raise Exception(f"Bucket name '{bucket_name}' is not allowed to be emptied.")
        
        response = supabase.storage.empty_bucket(bucket_name)
        if response.get("error"):
            raise Exception(f"Error emptying bucket: {response['error']['message']}")
           
        
    
    async def save_file(self, file: UploadFile, bucket_name:str,destination_path: str) -> str:
        """Saves an uploaded file to the specified destination path"""
        
        if not self.validate_bucket_name(bucket_name):
            raise Exception(f"Bucket name '{bucket_name}' is not allowed.")
        
        if not file.filename:
            raise Exception("File name is empty.")

        response = (
            supabase.storage
            .from_(bucket_name)
            .upload(
                path=f"{destination_path}/{file.filename}",
                file=file.file, 
                file_options={
                    "cache-control": "3600",
                    "upsert": False,
                    "content-type": file.content_type,
                },
            )
        )

        if response.get("error"):
            raise Exception(
                f"Error uploading file: {response['error']['message']}"
            )

    
    async def save_file_from_path(
        self,
        *,
        local_file_path: str,
        bucket_name: str,
        destination_path: str,
        content_type: str = "application/pdf",
        upsert: bool = False,   
    ) -> str:

        file_path = Path(local_file_path)

        try:
            with file_path.open("rb") as f:
                response = supabase.storage.from_(bucket_name).upload(
                    destination_path,
                    f,
                    file_options={
                        "content-type": content_type,
                        "upsert": "true" if upsert else "false",
                    },
                )

        except Exception as e:
            if isinstance(e, StorageException):
                raise Exception(f"Supabase Storage error: {str(e)}")

            raise Exception(f"Error uploading file: {str(e)}")

        # Return full path including bucket
        return f"{bucket_name}/{response.path}"


    
    async def save_files(
    self,
    files: List[str],      
    bucket_name: str,
    destination_path: str,):
        """Uploads files from disk to Supabase storage."""

        if not files:
            raise Exception("No files provided for upload.")

        if not self.validate_bucket_name(bucket_name):
            raise Exception(f"Bucket name '{bucket_name}' is not allowed.")

        for file_path in files:
            if not os.path.exists(file_path):
                raise Exception(f"File does not exist: {file_path}")

            file_name = os.path.basename(file_path)

            content_type, _ = mimetypes.guess_type(file_name)
            content_type = content_type or "application/octet-stream"

            with open(file_path, "rb") as f:
                response = (
                    supabase.storage
                    .from_(bucket_name)
                    .upload(
                        path=f"{destination_path}/{file_name}",
                        file=f,
                        file_options={
                            "cache-control": "3600",
                            "upsert": False,
                            "content-type": content_type,
                        },
                    )
                )

                print(response)
            if hasattr(response, "get") and response.get("error"):
                raise Exception(
                    f"Error uploading {file_name}: {response['error']['message']}"
                )
                
                            
    
    async def move_file(self, bucket_name: str, source_path: str, destination_path: str) -> None:
        """Moves a file within a Supabase storage bucket."""
        
        if not self.validate_bucket_name(bucket_name):
            raise Exception(f"Bucket name '{bucket_name}' is not allowed.")
        
        response = supabase.storage.from_(bucket_name).move(source_path, destination_path)
        
        if response.get("error"):
            raise Exception(f"Error moving file: {response['error']['message']}")


    async def save_json_file_from_data(
        self,
        data: dict,
        destination_path: str,
        filename: str = "data",
        bucket_name: str = "transcripts",
    ) -> str:
        """Saves a JSON file to Supabase storage from a dictionary.
        RETURNS the public URL of the uploaded file.
        """
        local_file_path = self.file_manager.create_json_file(data, filename)
        
        
        print(f"Uploading file {local_file_path} to bucket '{bucket_name}' at path '{destination_path}/{filename}'")
        full_path = await self.save_file_from_path(
            local_file_path=local_file_path,
            bucket_name=bucket_name,
            destination_path=f"{destination_path}/{filename}.json",
            content_type="application/json",
            upsert=True
        )
        
        # Clean up the temporary local file
        self.file_manager.cleanup_files([local_file_path])
        return full_path



    async def get_json_data_from_file_on_supabase(self, full_path: str) -> dict:
        """
        Example full_path:
        transcripts/<round_config_id>/<interview_id_transcript.json>.json
        """

        try:
            # full_path like 'transcripts/folder/file.json'
            parts = full_path.split("/", 1)
            if len(parts) != 2:
                raise Exception(f"Invalid full_path format: {full_path}. Expected 'bucket/path'")
            
            bucket_name, file_path = parts
            
            print(f"Fetching file from bucket '{bucket_name}' at path '{file_path}'")
            
            response = supabase.storage.from_(bucket_name).download(file_path)

            data = json.loads(response.decode("utf-8"))

            return data

        except Exception as e:
            raise Exception(f"Error fetching JSON from Supabase: {str(e)}")