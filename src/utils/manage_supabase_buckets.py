from configs.supabase_config import supabase
import os
import mimetypes
import tempfile
from pathlib import Path
from supabase import StorageException
from storage3.exceptions import StorageException


def download_to_tempfile(storage_path: str) -> str:
    """
    Downloads a file from Supabase storage to a temporary local file.

    Args:
        storage_path: Full path including bucket, e.g. "resumes/job_id/filename.pdf"

    Returns:
        Path to a temporary file containing the downloaded bytes.
        Caller is responsible for deleting it (use try/finally).
    """
    parts = storage_path.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid storage_path (expected 'bucket/path'): {storage_path!r}")

    bucket, path_in_bucket = parts
    data: bytes = supabase.storage.from_(bucket).download(path_in_bucket)

    suffix = os.path.splitext(path_in_bucket)[1] or ".pdf"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
    except Exception:
        os.unlink(tmp_path)
        raise

    return tmp_path


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

        response = None
        try:
            with file_path.open("rb") as f:
                response = supabase.storage.from_(bucket_name).upload(
                    destination_path,
                    f,
                    file_options={"content-type": "application/pdf"},
                )
        except StorageException as e:
            # File already exists → skip
            if "409" in str(e) or "Duplicate" in str(e):
                return f"{bucket_name}/{destination_path}"
            # Anything else is a real error
            raise

        # Different supabase/storage-py versions return different response shapes
        if hasattr(response, "error") and getattr(response, "error"):
            raise Exception(response.error.message)
        if isinstance(response, dict) and response.get("error"):
            raise Exception(response["error"].get("message") or "Error uploading file")

        return f"{bucket_name}/{destination_path}"
        

