from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class AskRequest(BaseModel):
    question: str
    top_k: Optional[int] = 4
    debug: Optional[bool] = False

class ProcessRequest(BaseModel):
    input: str
    top_k: Optional[int] = 4
    session_id: Optional[str] = None
    action: Optional[str] = None

class GroundingInfo(BaseModel):
    score: Optional[float] = None
    verdict: str

class SourceChunk(BaseModel):
    doc_name: str
    chunk_id: int
    section_title: Optional[str] = "General"
    text: str
    hybrid_score: Optional[float] = None
    rerank_score: Optional[float] = None

class AskResponse(BaseModel):
    answer: str
    answered: bool
    confidence: str
    grounding: GroundingInfo
    sources: List[SourceChunk]

class HealthResponse(BaseModel):
    status: str

class IngestResponse(BaseModel):
    status: str
    filename: str
    saved_text_file: str
    chunks_created: int
    documents_loaded: int
    message: Optional[str] = None

class ProcessResponse(BaseModel):
    mode: str
    status: str
    message: str
    session_id: Optional[str] = None
    question_result: Optional[Dict[str, Any]] = None
    ba_result: Optional[Dict[str, Any]] = None