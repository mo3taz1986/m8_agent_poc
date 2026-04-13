import re
from pathlib import Path

from pypdf import PdfReader


def normalize_pdf_text(text: str) -> str:
    """
    Clean extracted PDF text by normalizing whitespace and line breaks.
    """
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text_from_pdf(file_path: str | Path) -> str:
    """
    Extract text from a PDF file using pypdf.
    """
    reader = PdfReader(str(file_path))
    pages_text = []

    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            pages_text.append(page_text)

    full_text = "\n\n".join(pages_text)
    return normalize_pdf_text(full_text)