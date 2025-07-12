from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json
from ...core.database import get_db, MeetingMinutesDB, TranscriptionDB
from ...core.models import MeetingMinutes, ActionItem
from ...services.meeting_minutes import MeetingMinutesGenerator
from ...services.transcription import WhisperTranscriber

router = APIRouter()


@router.post("/generate")
async def generate_meeting_minutes(
    transcription_id: int,
    meeting_title: str = Body(...),
    meeting_date: datetime = Body(...),
    participants: List[str] = Body(...),
    db: Session = Depends(get_db)
):
    transcriber = WhisperTranscriber()
    transcription = transcriber.get_transcription(transcription_id, db)
    
    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")
        
    generator = MeetingMinutesGenerator()
    
    minutes = await generator.generate_minutes(
        transcription,
        meeting_title,
        meeting_date,
        participants
    )
    
    minutes_id = generator.save_minutes(minutes, db)
    
    from ...services.tagging import SmartTagger
    tagger = SmartTagger()
    
    db_minutes = db.query(MeetingMinutesDB).filter(MeetingMinutesDB.id == minutes_id).first()
    for action_item in db_minutes.action_items:
        tagger.tag_action_item(action_item.id, db)
        
    return {
        "meeting_minutes_id": minutes_id,
        "message": "Meeting minutes generated successfully"
    }


@router.get("/{minutes_id}")
async def get_meeting_minutes(
    minutes_id: int,
    db: Session = Depends(get_db)
):
    db_minutes = db.query(MeetingMinutesDB).filter(
        MeetingMinutesDB.id == minutes_id
    ).first()
    
    if not db_minutes:
        raise HTTPException(status_code=404, detail="Meeting minutes not found")
        
    action_items = []
    for db_item in db_minutes.action_items:
        tags = [tag.name for tag in db_item.tags]
        action_items.append({
            "id": db_item.id,
            "title": db_item.title,
            "description": db_item.description,
            "assignee": db_item.assignee,
            "due_date": db_item.due_date,
            "priority": db_item.priority,
            "status": db_item.status,
            "tags": tags,
            "confidence": db_item.confidence
        })
        
    return {
        "id": db_minutes.id,
        "meeting_title": db_minutes.meeting_title,
        "meeting_date": db_minutes.meeting_date,
        "participants": json.loads(db_minutes.participants),
        "summary": db_minutes.summary,
        "transcription_id": db_minutes.transcription_id,
        "action_items": action_items,
        "key_decisions": json.loads(db_minutes.key_decisions),
        "next_steps": json.loads(db_minutes.next_steps),
        "created_at": db_minutes.created_at
    }


@router.get("/")
async def list_meeting_minutes(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    minutes = db.query(MeetingMinutesDB).offset(skip).limit(limit).all()
    
    results = []
    for m in minutes:
        results.append({
            "id": m.id,
            "meeting_title": m.meeting_title,
            "meeting_date": m.meeting_date,
            "participants": json.loads(m.participants),
            "action_items_count": len(m.action_items),
            "created_at": m.created_at
        })
        
    return {
        "total": db.query(MeetingMinutesDB).count(),
        "items": results
    }


@router.get("/by-date")
async def get_meetings_by_date_range(
    start_date: datetime,
    end_date: datetime,
    db: Session = Depends(get_db)
):
    minutes = db.query(MeetingMinutesDB).filter(
        MeetingMinutesDB.meeting_date >= start_date,
        MeetingMinutesDB.meeting_date <= end_date
    ).all()
    
    results = []
    for m in minutes:
        results.append({
            "id": m.id,
            "meeting_title": m.meeting_title,
            "meeting_date": m.meeting_date,
            "participants": json.loads(m.participants),
            "action_items_count": len(m.action_items)
        })
        
    return results