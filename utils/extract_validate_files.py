import zipfile
import io
from fastapi import UploadFile, HTTPException, status
from services.errors.base import DomainError

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/zip",
    "application/x-zip-compressed",
}

MAX_FILE_SIZE_MB = 10
MAX_FILES = 20





async def validate_and_extract_files(
    files: list[UploadFile],
) -> list[UploadFile]:

    if not files:
        raise DomainError("No files uploaded", status.HTTP_400_BAD_REQUEST)

    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_FILES} files allowed",
        )

    extracted_pdfs: list[UploadFile] = []

    for file in files:
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise DomainError(
                f"Unsupported file type: {file.content_type}",
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )

        contents = await file.read()

        if len(contents) > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise DomainError(
                message=f"File size exceeds {MAX_FILE_SIZE_MB} MB: {file.filename}",
                status_code=413,
            )

        # Reset pointer for downstream use
        await file.seek(0)

        # ---- ZIP HANDLING ----
        if file.content_type.startswith("application/zip"):
            try:
                zip_bytes = io.BytesIO(contents)
                with zipfile.ZipFile(zip_bytes) as zip_file:
                    for name in zip_file.namelist():
                        if not name.lower().endswith(".pdf"):
                            continue

                        pdf_bytes = zip_file.read(name)
                        extracted_pdfs.append(
                            UploadFile(
                                filename=name,
                                file=io.BytesIO(pdf_bytes),
                                content_type="application/pdf",
                            )
                        )

            except zipfile.BadZipFile:
                raise DomainError(
                    f"Corrupted ZIP file: {file.filename}",
                    status.HTTP_400_BAD_REQUEST,
                )

        # ---- DIRECT PDF ----
        else:
            extracted_pdfs.append(file)

    if not extracted_pdfs:
        raise DomainError(
            "No valid PDF files found in the uploaded files",
            status.HTTP_400_BAD_REQUEST,
        )

    return extracted_pdfs
