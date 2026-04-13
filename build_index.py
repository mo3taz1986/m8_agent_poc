import json
import re
from typing import Dict, List

import numpy as np
from sentence_transformers import SentenceTransformer

from src.config import (
    DATA_DIR,
    INDEX_DIR,
    CHUNK_RECORDS_FILE,
    CHUNK_EMBEDDINGS_FILE,
    EMBEDDING_MODEL_NAME,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    MIN_CHUNK_CHAR_LENGTH,
)


def load_documents() -> Dict[str, str]:
    """
    Load all .txt documents from the data directory.
    """
    documents = {}
    for file_path in DATA_DIR.glob("*.txt"):
        documents[file_path.name] = file_path.read_text(encoding="utf-8")

    if not documents:
        raise ValueError("No .txt files found in data directory.")

    return documents


def normalize_whitespace(text: str) -> str:
    """
    Collapse repeated whitespace while preserving paragraph boundaries.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_into_sections(text: str) -> List[Dict[str, str]]:
    """
    Split document into sections using blank lines.
    If a paragraph looks like a heading, use it as section title.
    Otherwise assign a generic section title.
    """
    text = normalize_whitespace(text)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    sections = []
    current_title = "General"
    current_body_parts = []

    def flush_section():
        if current_body_parts:
            sections.append(
                {
                    "section_title": current_title,
                    "text": "\n\n".join(current_body_parts).strip(),
                }
            )

    for para in paragraphs:
        lines = [line.strip() for line in para.split("\n") if line.strip()]

        # Heuristic: short line without sentence-ending punctuation may be a heading
        if len(lines) == 1:
            candidate = lines[0]
            is_heading = (
                len(candidate) <= 80
                and not candidate.endswith(".")
                and not candidate.endswith("!")
                and not candidate.endswith("?")
            )
            if is_heading:
                flush_section()
                current_title = candidate
                current_body_parts = []
                continue

        current_body_parts.append(para)

    flush_section()

    if not sections:
        sections = [{"section_title": "General", "text": text}]

    return sections


def sentence_split(text: str) -> List[str]:
    """
    Basic sentence splitter for policy-style text.
    """
    text = text.replace("\n", " ").strip()
    if not text:
        return []

    # Split on punctuation followed by whitespace
    parts = re.split(r"(?<=[.!?])\s+", text)
    sentences = [p.strip() for p in parts if p.strip()]
    return sentences


def chunk_sentences(
    sentences: List[str],
    chunk_size: int,
    overlap: int,
    min_chunk_char_length: int,
) -> List[str]:
    """
    Chunk sentences with overlap.
    """
    if not sentences:
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks = []
    step = chunk_size - overlap

    for start_idx in range(0, len(sentences), step):
        chunk_sentences_list = sentences[start_idx:start_idx + chunk_size]
        if not chunk_sentences_list:
            continue

        chunk_text = " ".join(chunk_sentences_list).strip()
        if len(chunk_text) >= min_chunk_char_length:
            chunks.append(chunk_text)

        if start_idx + chunk_size >= len(sentences):
            break

    return chunks


def build_chunk_records(documents: Dict[str, str]) -> List[Dict]:
    """
    Build enriched chunk records with document and section metadata.
    """
    records = []

    for doc_name, full_text in documents.items():
        sections = split_into_sections(full_text)

        for section_idx, section in enumerate(sections):
            section_title = section["section_title"]
            section_text = section["text"]

            sentences = sentence_split(section_text)
            chunks = chunk_sentences(
                sentences=sentences,
                chunk_size=CHUNK_SIZE,
                overlap=CHUNK_OVERLAP,
                min_chunk_char_length=MIN_CHUNK_CHAR_LENGTH,
            )

            for chunk_idx, chunk_text in enumerate(chunks):
                records.append(
                    {
                        "doc_name": doc_name,
                        "section_title": section_title,
                        "section_id": section_idx,
                        "chunk_id": chunk_idx,
                        "text": chunk_text,
                    }
                )

    return records


def main():
    INDEX_DIR.mkdir(exist_ok=True)

    documents = load_documents()
    records = build_chunk_records(documents)

    if not records:
        raise ValueError("No chunk records were created. Check source documents.")

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    embeddings = model.encode(
        [record["text"] for record in records],
        convert_to_numpy=True,
    )

    with CHUNK_RECORDS_FILE.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    np.save(CHUNK_EMBEDDINGS_FILE, embeddings)

    print(f"Loaded {len(documents)} documents")
    print(f"Built {len(records)} chunk records")
    print(f"Saved chunk records to {CHUNK_RECORDS_FILE}")
    print(f"Saved embeddings to {CHUNK_EMBEDDINGS_FILE}")


if __name__ == "__main__":
    main()