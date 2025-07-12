from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ...core.database import get_db, TagDB, ActionItemDB
from ...services.tagging import SmartTagger

router = APIRouter()


@router.get("/")
async def list_tags(
    category: str = None,
    db: Session = Depends(get_db)
):
    query = db.query(TagDB)
    
    if category:
        query = query.filter(TagDB.category == category)
        
    tags = query.all()
    
    results = []
    for tag in tags:
        results.append({
            "id": tag.id,
            "name": tag.name,
            "category": tag.category,
            "color": tag.color,
            "description": tag.description,
            "usage_count": len(tag.action_items)
        })
        
    return sorted(results, key=lambda x: x["usage_count"], reverse=True)


@router.get("/statistics")
async def get_tag_statistics(db: Session = Depends(get_db)):
    tagger = SmartTagger()
    return tagger.get_tag_statistics(db)


@router.get("/suggest")
async def suggest_tags(
    query: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    tagger = SmartTagger()
    suggestions = tagger.suggest_tags(query, db, limit)
    return {"suggestions": suggestions}


@router.post("/retag-all")
async def retag_all_items(db: Session = Depends(get_db)):
    tagger = SmartTagger()
    results = tagger.tag_all_action_items(db)
    return results


@router.get("/categories")
async def get_tag_categories(db: Session = Depends(get_db)):
    categories = db.query(TagDB.category).distinct().all()
    return {"categories": [c[0] for c in categories]}


@router.get("/{tag_name}/items")
async def get_items_by_tag(
    tag_name: str,
    db: Session = Depends(get_db)
):
    tag = db.query(TagDB).filter(TagDB.name == tag_name).first()
    
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
        
    results = []
    for item in tag.action_items:
        results.append({
            "id": item.id,
            "title": item.title,
            "assignee": item.assignee,
            "due_date": item.due_date,
            "priority": item.priority,
            "status": item.status
        })
        
    return {
        "tag": tag_name,
        "category": tag.category,
        "total_items": len(results),
        "items": results
    }