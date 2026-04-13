import json
import re
from pathlib import Path

from src.config import CHUNK_RECORDS_FILE, BM25_INDEX_FILE, INDEX_DIR


def tokenize(text: str) -> list[str]:
    """
    Simple tokenizer for BM25 corpus persistence.
    Lowercases and keeps alphanumeric word tokens.
    """
    return re.findall(r"\b\w+\b", text.lower())


def main():
    if not CHUNK_RECORDS_FILE.exists():
        raise FileNotFoundError(
            f"Chunk records not found at {CHUNK_RECORDS_FILE}. Run build_index first."
        )

    with CHUNK_RECORDS_FILE.open("r", encoding="utf-8") as f:
        records = json.load(f)

    tokenized_corpus = [tokenize(record["text"]) for record in records]

    INDEX_DIR.mkdir(exist_ok=True)

    with BM25_INDEX_FILE.open("w", encoding="utf-8") as f:
        json.dump(tokenized_corpus, f, indent=2)

    print(f"Loaded {len(records)} chunk records")
    print(f"Saved BM25 corpus to {BM25_INDEX_FILE}")


if __name__ == "__main__":
    main()