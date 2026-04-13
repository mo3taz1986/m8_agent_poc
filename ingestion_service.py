from pathlib import Path

from src.config import (
    UPLOAD_DIR,
    INGESTED_TEXT_DIR,
    SUPPORTED_EXTENSIONS,
)
from src.services.index_service import rebuild_indexes
from src.utils.pdf_loader import extract_text_from_pdf


def ensure_ingestion_directories() -> None:
    UPLOAD_DIR.mkdir(exist_ok=True)
    INGESTED_TEXT_DIR.mkdir(parents=True, exist_ok=True)


def save_extracted_text_as_txt(source_filename: str, text: str) -> Path:
    """
    Save extracted text into the ingested text corpus folder as a .txt file.
    """
    stem = Path(source_filename).stem
    target_path = INGESTED_TEXT_DIR / f"{stem}.txt"
    target_path.write_text(text, encoding="utf-8")
    return target_path


def ingest_file(file_path: str | Path) -> dict:
    """
    Ingest a supported file, convert it to text corpus if needed,
    then rebuild indexes.
    """
    ensure_ingestion_directories()

    file_path = Path(file_path)
    extension = file_path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {extension}")

    if extension == ".pdf":
        extracted_text = extract_text_from_pdf(file_path)

        if not extracted_text.strip():
            raise ValueError("No readable text could be extracted from the PDF.")

        saved_txt_path = save_extracted_text_as_txt(file_path.name, extracted_text)

    elif extension == ".txt":
        text = file_path.read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError("Uploaded text file is empty.")

        saved_txt_path = save_extracted_text_as_txt(file_path.name, text)

    else:
        raise ValueError(f"File type not yet implemented: {extension}")

    rebuild_result = rebuild_indexes()

    return {
        "status": "success",
        "filename": file_path.name,
        "saved_text_file": str(saved_txt_path),
        "chunks_created": rebuild_result["chunks_created"],
        "documents_loaded": rebuild_result["documents_loaded"],
        "message": "File ingested and indexes rebuilt successfully.",
    }