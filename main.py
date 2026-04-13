from fastapi import FastAPI
from src.api.routes import router

app = FastAPI(
    title="Governance Retrieval Assistant API",
    version="6.0.0"
)

app.include_router(router)