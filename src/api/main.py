from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from ..core.config import settings
from ..core.database import init_db
from .routers import terms, transcription, meetings, action_items, tags

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    init_db()
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="Action Items API",
    description="Speech transcription and action item generation for construction industry",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(terms.router, prefix=f"{settings.api_prefix}/terms", tags=["terms"])
app.include_router(transcription.router, prefix=f"{settings.api_prefix}/transcription", tags=["transcription"])
app.include_router(meetings.router, prefix=f"{settings.api_prefix}/meetings", tags=["meetings"])
app.include_router(action_items.router, prefix=f"{settings.api_prefix}/action-items", tags=["action-items"])
app.include_router(tags.router, prefix=f"{settings.api_prefix}/tags", tags=["tags"])


@app.get("/")
async def root():
    return {
        "message": "Action Items API",
        "version": "0.1.0",
        "docs": f"{settings.api_prefix}/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}