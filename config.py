from pathlib import Path
import os
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ROOT_DIR / ".env")

DATA_DIR = ROOT_DIR / "data"
INDEX_DIR = ROOT_DIR / "index"
OUTPUT_DIR = ROOT_DIR / "output"
UPLOAD_DIR = ROOT_DIR / "uploads"
INGESTED_TEXT_DIR = DATA_DIR / "ingested"

CHUNK_RECORDS_FILE = INDEX_DIR / "chunk_records.json"
CHUNK_EMBEDDINGS_FILE = INDEX_DIR / "chunk_embeddings.npy"
BM25_INDEX_FILE = INDEX_DIR / "bm25_corpus.json"
LOG_FILE = OUTPUT_DIR / "interaction_log.jsonl"
BA_SESSION_STORE_FILE = OUTPUT_DIR / "ba_sessions.json"

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
CLAUDE_MODEL_NAME = "claude-sonnet-4-20250514"

CHUNK_SIZE = 3
CHUNK_OVERLAP = 1
MIN_CHUNK_CHAR_LENGTH = 40

TOP_K = 3
SIMILARITY_THRESHOLD = 0.35
SEMANTIC_TOP_K = 10
KEYWORD_TOP_K = 10
HYBRID_TOP_K = 8
FINAL_TOP_K = 4

SEMANTIC_WEIGHT = 0.6
KEYWORD_WEIGHT = 0.4
HYBRID_WEIGHT = 0.7
TERM_COVERAGE_WEIGHT = 0.3

MIN_HYBRID_SCORE_TO_ANSWER = 0.20
MIN_RERANK_SCORE_TO_ANSWER = 0.20
MAX_CONTEXT_CHUNKS = 4

ENABLE_GROUNDING_CHECK = True
MIN_GROUNDING_SCORE_TO_ACCEPT = 0.20

SUPPORTED_EXTENSIONS = {".txt", ".pdf"}

# ── Jira ──────────────────────────────────────────────────────────────────────
JIRA_BASE_URL        = os.getenv("JIRA_BASE_URL", "").rstrip("/")
JIRA_EMAIL           = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN       = os.getenv("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY     = os.getenv("JIRA_PROJECT_KEY", "")
JIRA_EPIC_ISSUE_TYPE = os.getenv("JIRA_EPIC_ISSUE_TYPE", "Epic")
JIRA_STORY_ISSUE_TYPE= os.getenv("JIRA_STORY_ISSUE_TYPE", "Story")

# ── Session store (Step 5) ────────────────────────────────────────────────────
# REDIS_URL — connection string for persistent sessions.
# Leave empty to use the in-memory fallback (sessions lost on restart).
# Examples:
#   Local Redis:           redis://localhost:6379/0
#   Redis with password:   redis://:yourpassword@localhost:6379/0
REDIS_URL = os.getenv("REDIS_URL", "")

# How long a session lives without activity before Redis expires it.
# Default: 86400 seconds (24 hours). Resets on every session write.
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "86400"))
