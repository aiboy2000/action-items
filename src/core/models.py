from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class TermType(str, Enum):
    TECHNICAL = "technical"
    MATERIAL = "material"
    PROCESS = "process"
    SAFETY = "safety"
    EQUIPMENT = "equipment"
    OTHER = "other"


class Term(BaseModel):
    id: Optional[int] = None
    term: str
    reading: Optional[str] = None
    definition: Optional[str] = None
    term_type: TermType
    source_document: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    
class TranscriptionSegment(BaseModel):
    text: str
    start_time: float
    end_time: float
    confidence: float
    speaker: Optional[str] = None
    corrected_text: Optional[str] = None
    

class TranscriptionResult(BaseModel):
    id: Optional[int] = None
    file_name: str
    original_text: str
    corrected_text: str
    segments: List[TranscriptionSegment]
    duration: float
    language: str = "ja"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    

class ActionItemPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ActionItemStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ActionItem(BaseModel):
    id: Optional[int] = None
    title: str
    description: str
    assignee: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: ActionItemPriority
    status: ActionItemStatus = ActionItemStatus.PENDING
    tags: List[str] = Field(default_factory=list)
    source_segment: Optional[TranscriptionSegment] = None
    confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    

class MeetingMinutes(BaseModel):
    id: Optional[int] = None
    meeting_title: str
    meeting_date: datetime
    participants: List[str]
    summary: str
    transcription_id: int
    action_items: List[ActionItem]
    key_decisions: List[str]
    next_steps: List[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    

class Tag(BaseModel):
    id: Optional[int] = None
    name: str
    category: str
    color: Optional[str] = None
    description: Optional[str] = None
    

class ProcessingStatus(BaseModel):
    task_id: str
    status: str
    progress: float = Field(ge=0.0, le=1.0)
    message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None