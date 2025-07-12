from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json
from ...core.database import get_db, ActionItemDB, TagDB
from ...core.models import ActionItemStatus, ActionItemPriority
from ...services.tagging import SmartTagger

router = APIRouter()


@router.get("/")
async def list_action_items(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assignee: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(ActionItemDB)
    
    if status:
        query = query.filter(ActionItemDB.status == status)
    if priority:
        query = query.filter(ActionItemDB.priority == priority)
    if assignee:
        query = query.filter(ActionItemDB.assignee == assignee)
        
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    
    results = []
    for item in items:
        tags = [tag.name for tag in item.tags]
        results.append({
            "id": item.id,
            "title": item.title,
            "description": item.description,
            "assignee": item.assignee,
            "due_date": item.due_date,
            "priority": item.priority,
            "status": item.status,
            "tags": tags,
            "confidence": item.confidence,
            "created_at": item.created_at,
            "updated_at": item.updated_at
        })
        
    return {
        "total": total,
        "items": results
    }


@router.get("/{item_id}")
async def get_action_item(
    item_id: int,
    db: Session = Depends(get_db)
):
    item = db.query(ActionItemDB).filter(ActionItemDB.id == item_id).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")
        
    tags = [tag.name for tag in item.tags]
    source_segment = json.loads(item.source_segment) if item.source_segment else None
    
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "assignee": item.assignee,
        "due_date": item.due_date,
        "priority": item.priority,
        "status": item.status,
        "tags": tags,
        "source_segment": source_segment,
        "confidence": item.confidence,
        "meeting_minutes_id": item.meeting_minutes_id,
        "created_at": item.created_at,
        "updated_at": item.updated_at
    }


@router.patch("/{item_id}/status")
async def update_action_item_status(
    item_id: int,
    status: ActionItemStatus = Body(...),
    db: Session = Depends(get_db)
):
    item = db.query(ActionItemDB).filter(ActionItemDB.id == item_id).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")
        
    item.status = status.value
    db.commit()
    
    return {"message": "Status updated successfully"}


@router.patch("/{item_id}")
async def update_action_item(
    item_id: int,
    title: Optional[str] = Body(None),
    description: Optional[str] = Body(None),
    assignee: Optional[str] = Body(None),
    due_date: Optional[datetime] = Body(None),
    priority: Optional[ActionItemPriority] = Body(None),
    db: Session = Depends(get_db)
):
    item = db.query(ActionItemDB).filter(ActionItemDB.id == item_id).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")
        
    if title is not None:
        item.title = title
    if description is not None:
        item.description = description
    if assignee is not None:
        item.assignee = assignee
    if due_date is not None:
        item.due_date = due_date
    if priority is not None:
        item.priority = priority.value
        
    db.commit()
    
    tagger = SmartTagger()
    tagger.tag_action_item(item_id, db)
    
    return {"message": "Action item updated successfully"}


@router.get("/{item_id}/related")
async def get_related_items(
    item_id: int,
    limit: int = 5,
    db: Session = Depends(get_db)
):
    tagger = SmartTagger()
    related = tagger.find_related_items(item_id, db, limit)
    
    results = []
    for item in related:
        tags = [tag.name for tag in item.tags]
        results.append({
            "id": item.id,
            "title": item.title,
            "assignee": item.assignee,
            "priority": item.priority,
            "status": item.status,
            "tags": tags
        })
        
    return results


@router.get("/by-tags")
async def search_by_tags(
    tags: str,
    db: Session = Depends(get_db)
):
    tag_list = tags.split(",")
    tagger = SmartTagger()
    items = tagger.search_by_tags(tag_list, db)
    
    results = []
    for item in items:
        item_tags = [tag.name for tag in item.tags]
        results.append({
            "id": item.id,
            "title": item.title,
            "assignee": item.assignee,
            "due_date": item.due_date,
            "priority": item.priority,
            "status": item.status,
            "tags": item_tags
        })
        
    return results


@router.get("/overdue")
async def get_overdue_items(
    db: Session = Depends(get_db)
):
    now = datetime.now()
    items = db.query(ActionItemDB).filter(
        ActionItemDB.due_date < now,
        ActionItemDB.status != "completed",
        ActionItemDB.status != "cancelled"
    ).all()
    
    results = []
    for item in items:
        tags = [tag.name for tag in item.tags]
        days_overdue = (now - item.due_date).days
        
        results.append({
            "id": item.id,
            "title": item.title,
            "assignee": item.assignee,
            "due_date": item.due_date,
            "days_overdue": days_overdue,
            "priority": item.priority,
            "status": item.status,
            "tags": tags
        })
        
    return sorted(results, key=lambda x: x["days_overdue"], reverse=True)