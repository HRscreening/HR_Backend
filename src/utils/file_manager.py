import io
import os
import re
import shutil
import tempfile
import unicodedata
import zipfile
from fastapi import UploadFile, status
from typing import List
from src.services.errors.base import DomainError
from configs.env_config import BASE_UPLOAD_DIR, SUPABASE_PUBLIC_URL
from src.utils.manage_supabase_buckets import save_file_from_path
import json




class FileManagerService:
    BASE_TEMP_DIR = os.path.abspath(os.path.join(os.getcwd(), "data", "temp"))
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

    def sanitize_filename(self, filename: str) -> str:
        """
        Make a Supabase-safe object key component.
        Keeps extension, strips/normalizes unicode, replaces unsafe chars with '_'.
        """
        if not filename:
            return "uploaded_file"

        base = os.path.basename(filename)
        name, ext = os.path.splitext(base)
        ext = (ext or "").lower()

        # Normalize unicode (e.g., “–” -> "-"), then drop non-ascii
        name = unicodedata.normalize("NFKD", name)
        name = name.encode("ascii", "ignore").decode("ascii")

        # Replace any run of unsafe chars with underscore
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._-")
        name = re.sub(r"_+", "_", name)

        if not name:
            name = "uploaded_file"

        # Keep keys reasonably short (avoid storage limits / ugly URLs)
        if len(name) > 120:
            name = name[:120]

        # Default to .pdf if no extension
        if not ext:
            ext = ".pdf"

        return f"{name}{ext}"

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
    ) -> tuple[str, list[str]]:
        """
        Streams uploaded files to disk for later background processing.
        Returns (job_dir, list of saved file paths).
        """

        job_dir = os.path.join(BASE_UPLOAD_DIR, dir_name)
        os.makedirs(job_dir, exist_ok=True)

        saved_paths: list[str] = []
        used_names: set[str] = set()

        for file in files:
            if not file.filename:
                raise ValueError("File name is empty")

            self._validate_extension(file.filename)

            safe_filename = self.sanitize_filename(file.filename)
            # Ensure unique filenames within this batch to avoid overwriting (common in zips: resume.pdf).
            base, ext = os.path.splitext(safe_filename)
            candidate = safe_filename
            i = 1
            while candidate.lower() in used_names:
                i += 1
                candidate = f"{base}_{i}{ext}"
            used_names.add(candidate.lower())

            dest_path = os.path.join(job_dir, candidate)

            with open(dest_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            saved_paths.append(dest_path)

        return job_dir, saved_paths

    async def upload(self, file: UploadFile, destination_path: str) -> tuple[str, str]:
        """
        Upload a single file to Supabase storage (resumes bucket).
        Supabase storage client expects a file path (it calls open(path, "rb")), so we
        write the UploadFile to a temp file, upload via save_file_from_path, then remove it.
        destination_path: path prefix inside bucket, e.g. "jds/{job_id}" (no trailing slash).
        Returns (public_url, stored_filename).
        """
        if not file.filename:
            raise ValueError("File name is empty")
        self._validate_extension(file.filename)

        safe_filename = self.sanitize_filename(file.filename)
        await file.seek(0)
        contents = await file.read()
        await file.seek(0)

        suffix = os.path.splitext(safe_filename)[1] or ".pdf"
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(contents)
            # destination_path inside bucket must include filename for save_file_from_path
            bucket_dest = f"{destination_path.rstrip('/')}/{safe_filename}"
            save_file_from_path(
                local_file_path=tmp_path,
                bucket_name="resumes",
                destination_path=bucket_dest,
            )
            storage_path = f"resumes/{bucket_dest}"
            return f"{SUPABASE_PUBLIC_URL}/{storage_path}", safe_filename
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

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
        used_names: set[str] = set()

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
                    # Skip common macOS junk entries that duplicate real files
                    base = os.path.basename(name)
                    if (
                        name.startswith("__MACOSX/")
                        or "/__MACOSX/" in name
                        or base in {".DS_Store"}
                        or base.startswith("._")
                        or not base
                    ):
                        continue
                    self._validate_extension(name)

                # extract after validation
                for name in names:
                    if name.endswith("/"):
                        continue

                    base = os.path.basename(name)
                    if (
                        name.startswith("__MACOSX/")
                        or "/__MACOSX/" in name
                        or base in {".DS_Store"}
                        or base.startswith("._")
                        or not base
                    ):
                        continue

                    safe_name = self.sanitize_filename(base)
                    # Ensure uniqueness to avoid overwriting when multiple files share a name.
                    root, ext = os.path.splitext(safe_name)
                    candidate = safe_name
                    i = 1
                    while candidate.lower() in used_names:
                        i += 1
                        candidate = f"{root}_{i}{ext}"
                    used_names.add(candidate.lower())

                    extracted.append(
                        UploadFile(
                            filename=candidate,
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

    def create_json_file(self, data: dict, filename: str) -> str:
        safe_filename = self.sanitize_filename(filename)

        base_dir = os.path.join(os.getcwd(), "data", "temp")
        os.makedirs(base_dir, exist_ok=True)

        path = os.path.join(base_dir, f"{safe_filename}.json")

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return path
    
    
    def cleanup_files(self, file_paths: List[str]) -> None:
        """Delete files only inside data/temp directory."""

        for path in file_paths:
            if not path:
                continue

            try:
                abs_path = os.path.abspath(path)

                # 🔒 Security check: ensure file is inside allowed directory
                if not abs_path.startswith(self.BASE_TEMP_DIR):
                    print(f"⚠️ Skipping deletion (outside allowed dir): {abs_path}")
                    continue

                if os.path.exists(abs_path):
                    os.remove(abs_path)

            except Exception as e:
                print(f"⚠️ Failed to delete file: {path}, error: {e}")
            
fileManager = FileManagerService()