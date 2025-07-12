from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
from pathlib import Path
import shutil
import uuid
from datetime import datetime
from ...core.database import get_db
from ...core.models import ProcessingStatus
from ...services.transcription import WhisperTranscriber
from ...core.config import settings

router = APIRouter()

processing_status = {}


@router.post("/transcribe")
async def transcribe_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    apply_correction: bool = True,
    language: str = "ja",
    db: Session = Depends(get_db)
):
    supported_formats = ['.mp3', '.mp4', '.wav', '.m4a', '.flac', '.ogg']
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in supported_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Supported: {', '.join(supported_formats)}"
        )
        
    task_id = str(uuid.uuid4())
    
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(exist_ok=True)
    
    temp_file = upload_dir / f"{task_id}{file_ext}"
    
    with temp_file.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    processing_status[task_id] = ProcessingStatus(
        task_id=task_id,
        status="processing",
        progress=0.0,
        message="Transcription started",
        started_at=datetime.now()
    )
    
    async def process_transcription():
        try:
            transcriber = WhisperTranscriber()
            
            processing_status[task_id].progress = 0.3
            processing_status[task_id].message = "Loading model..."
            
            result = await transcriber.transcribe_file(temp_file, apply_correction)
            
            processing_status[task_id].progress = 0.8
            processing_status[task_id].message = "Saving results..."
            
            transcription_id = transcriber.save_transcription(result, db)
            
            processing_status[task_id].status = "completed"
            processing_status[task_id].progress = 1.0
            processing_status[task_id].result = {"transcription_id": transcription_id}
            processing_status[task_id].completed_at = datetime.now()
            
            temp_file.unlink()
            
        except Exception as e:
            processing_status[task_id].status = "failed"
            processing_status[task_id].error = str(e)
            processing_status[task_id].completed_at = datetime.now()
            
            if temp_file.exists():
                temp_file.unlink()
                
    background_tasks.add_task(process_transcription)
    
    return {
        "task_id": task_id,
        "message": "Transcription task created",
        "status_url": f"/api/v1/transcription/status/{task_id}"
    }


@router.get("/status/{task_id}")
async def get_transcription_status(task_id: str):
    if task_id not in processing_status:
        raise HTTPException(status_code=404, detail="Task not found")
        
    return processing_status[task_id]


@router.get("/{transcription_id}")
async def get_transcription(
    transcription_id: int,
    db: Session = Depends(get_db)
):
    transcriber = WhisperTranscriber()
    result = transcriber.get_transcription(transcription_id, db)
    
    if not result:
        raise HTTPException(status_code=404, detail="Transcription not found")
        
    return result


@router.post("/correct-text")
async def correct_text(
    text: str,
    confidence_threshold: float = 0.85
):
    from ...services.vector_search import VectorSearchEngine, TermCorrector
    
    vector_engine = VectorSearchEngine()
    corrector = TermCorrector(vector_engine)
    
    corrected_text, corrections = corrector.correct_text(text, confidence_threshold)
    
    return {
        "original_text": text,
        "corrected_text": corrected_text,
        "corrections": corrections
    }