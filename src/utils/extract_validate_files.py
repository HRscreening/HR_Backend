# import io
# import zipfile
# from fastapi import UploadFile, status
# from src.services.errors.base import DomainError
# import os

# ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}
# ZIP_MIME_TYPES = {
#     "application/zip",
#     "application/x-zip-compressed",
#     "multipart/x-zip",
# }
# ALLOWED_MIME_TYPES = ZIP_MIME_TYPES | {
#     "application/pdf",
#     "application/msword",
#     "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
# }

# MAX_FILES = 100
# MAX_FILE_SIZE_MB = 5
# MAX_ZIP_FILES = 200


# async def validate_and_extract_files(
#     files: list[UploadFile],
# ) -> list[UploadFile]:

#     if not files:
#         raise DomainError("No files uploaded", status.HTTP_400_BAD_REQUEST)

#     if len(files) > MAX_FILES:
#         raise DomainError(
#             f"Maximum {MAX_FILES} files allowed",
#             status.HTTP_400_BAD_REQUEST,
#         )

#     extracted_files: list[UploadFile] = []

#     for file in files:
#         if file.content_type not in ALLOWED_MIME_TYPES:
#             raise DomainError(
#                 f"Unsupported file type: {file.content_type}",
#                 status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
#             )

#         contents = await file.read()

#         if len(contents) > MAX_FILE_SIZE_MB * 1024 * 1024:
#             raise DomainError(
#                 f"File size exceeds {MAX_FILE_SIZE_MB} MB: {file.filename}",
#                 status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
#             )

#         await file.seek(0)

#         # ---------- ZIP ----------
#         if file.content_type in ZIP_MIME_TYPES:
#             try:
#                 with zipfile.ZipFile(io.BytesIO(contents)) as zip_file:
#                     names = zip_file.namelist()

#                     if not names:
#                         raise DomainError("ZIP file is empty", 400)

#                     if len(names) > MAX_ZIP_FILES:
#                         raise DomainError("Too many files inside ZIP", 400)

#                     # validate ALL first
#                     for name in names:
#                         if name.endswith("/"):
#                             continue
#                         ext = "." + name.lower().rsplit(".", 1)[-1]
#                         if ext not in ALLOWED_EXTENSIONS:
#                             raise DomainError(
#                                 f"Unsupported file in ZIP: {name}",
#                                 status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
#                             )

#                     # extract only if valid
#                     for name in names:
#                         if name.endswith("/"):
#                             continue
#                         safe_name = os.path.basename(name)
#                         extracted_files.append(
#                             UploadFile(
#                                 filename=safe_name,
#                                 file=io.BytesIO(zip_file.read(name)),
#                             )
#                         )

#             except zipfile.BadZipFile:
#                 raise DomainError(
#                     f"Corrupted ZIP file: {file.filename}",
#                     status.HTTP_400_BAD_REQUEST,
#                 )

#         # ---------- DIRECT FILE ----------
#         else:
#             ext = "." + file.filename.lower().rsplit(".", 1)[-1]
#             if ext not in ALLOWED_EXTENSIONS:
#                 raise DomainError(
#                     f"Unsupported file format: {file.filename}",
#                     status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
#                 )

#             extracted_files.append(file)

#     if not extracted_files:
#         raise DomainError("No valid files found", status.HTTP_400_BAD_REQUEST)

#     return extracted_files






import io
import os
import shutil
import zipfile
from fastapi import UploadFile, status
from typing import List
from src.services.errors.base import DomainError
from configs.env_config import BASE_UPLOAD_DIR





class FileManager:
    ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}

    ZIP_MIME_TYPES = {
        "application/zip",
        "application/x-zip-compressed",
        "multipart/x-zip",
    }

    ALLOWED_MIME_TYPES = ZIP_MIME_TYPES | {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    MAX_FILES = 100
    MAX_FILE_SIZE_MB = 5
    MAX_ZIP_FILES = 200

    async def validate_and_extract(
        self,
        files: List[UploadFile],
    ) -> List[UploadFile]:

        if not files:
            raise DomainError("No files uploaded", status.HTTP_400_BAD_REQUEST)

        if len(files) > self.MAX_FILES:
            raise DomainError(
                f"Maximum {self.MAX_FILES} files allowed",
                status.HTTP_400_BAD_REQUEST,
            )

        extracted_files: List[UploadFile] = []

        for file in files:
            await self._validate_file_mime(file)

            contents = await self._read_and_validate_size(file)

            if file.content_type in self.ZIP_MIME_TYPES:
                extracted_files.extend(
                    self._extract_zip_files(contents)
                )
            else:
                self._validate_extension(file.filename)
                extracted_files.append(file)

        if not extracted_files:
            raise DomainError("No valid files found", status.HTTP_400_BAD_REQUEST)

        return extracted_files

    async def stage_uploaded_files(
        self,
        dir_name: str,
        files: List[UploadFile],
    ) -> list[str]:
        """
        Streams uploaded files to disk for later background processing.
        Returns list of saved file paths.
        """

        job_dir = os.path.join(BASE_UPLOAD_DIR, dir_name)
        os.makedirs(job_dir, exist_ok=True)

        saved_paths: list[str] = []

        for file in files:
            if not file.filename:
                raise ValueError("File name is empty")

            ext = file.filename.rsplit(".", 1)[-1].lower()
            if ext not in self.ALLOWED_EXTENSIONS:
                raise ValueError(f"Unsupported file type: {file.filename}")

            dest_path = os.path.join(job_dir, file.filename)
            
            
            with open(dest_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            saved_paths.append(dest_path)

        return job_dir,saved_paths
    
    
    # ------------------ helpers ------------------

    async def _read_and_validate_size(self, file: UploadFile) -> bytes:
        contents = await file.read()

        if len(contents) > self.MAX_FILE_SIZE_MB * 1024 * 1024:
            raise DomainError(
                f"File size exceeds {self.MAX_FILE_SIZE_MB} MB: {file.filename}",
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        await file.seek(0)
        return contents

    async def _validate_file_mime(self, file: UploadFile) -> None:
        if file.content_type not in self.ALLOWED_MIME_TYPES:
            raise DomainError(
                f"Unsupported file type: {file.content_type}",
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )

    def _extract_zip_files(self, contents: bytes) -> List[UploadFile]:
        extracted: List[UploadFile] = []

        try:
            with zipfile.ZipFile(io.BytesIO(contents)) as zip_file:
                names = zip_file.namelist()

                if not names:
                    raise DomainError("ZIP file is empty", 400)

                if len(names) > self.MAX_ZIP_FILES:
                    raise DomainError("Too many files inside ZIP", 400)

                # validate first
                for name in names:
                    if name.endswith("/"):
                        continue
                    self._validate_extension(name)

                # extract after validation
                for name in names:
                    if name.endswith("/"):
                        continue

                    safe_name = os.path.basename(name)
                    extracted.append(
                        UploadFile(
                            filename=safe_name,
                            file=io.BytesIO(zip_file.read(name)),
                        )
                    )

        except zipfile.BadZipFile:
            raise DomainError(
                "Corrupted ZIP file",
                status.HTTP_400_BAD_REQUEST,
            )

        return extracted

    def _validate_extension(self, filename: str) -> None:
        ext = "." + filename.lower().rsplit(".", 1)[-1]
        if ext not in self.ALLOWED_EXTENSIONS:
            raise DomainError(
                f"Unsupported file format: {filename}",
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )
