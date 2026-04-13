from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File

from src.api.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    IngestResponse,
    ProcessRequest,
    ProcessResponse,
)
from src.services.answer_service import ask_question
from src.services.ingestion_service import ingest_file
from src.services.intake_service import process_input
from src.config import UPLOAD_DIR

router = APIRouter()

@router.get("/")
def root():
    return {"message": "Governance Retrieval Assistant API is running."}

@router.get("/health", response_model=HealthResponse)
def health_check():
    return {"status": "ok"}

@router.post("/ask", response_model=AskResponse)
def ask_endpoint(payload: AskRequest):
    question = payload.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    try:
        result = ask_question(question=question, top_k=payload.top_k or 4)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid ask request: {str(e)}")
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Required index file missing: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ask request failed: {str(e)}")

@router.post("/process", response_model=ProcessResponse)
def process_endpoint(payload: ProcessRequest):
    user_input = (payload.input or "").strip()

    try:
        result = process_input(
            user_input=user_input,
            top_k=payload.top_k or 4,
            session_id=payload.session_id,
            action=payload.action,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid process request: {str(e)}")
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Required index file missing: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Process request failed: {str(e)}")

@router.post("/ingest", response_model=IngestResponse)
async def ingest_endpoint(file: UploadFile = File(...)):
    try:
        UPLOAD_DIR.mkdir(exist_ok=True)

        filename = Path(file.filename).name
        if not filename:
            raise ValueError("Uploaded file must have a valid name.")

        saved_path = UPLOAD_DIR / filename

        content = await file.read()
        if not content:
            raise ValueError("Uploaded file is empty.")

        saved_path.write_bytes(content)

        result = ingest_file(saved_path)
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Required file or directory missing: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")