from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.sql import func
from typing import Generator
from .config import settings

Base = declarative_base()

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


action_item_tags = Table(
    'action_item_tags',
    Base.metadata,
    Column('action_item_id', Integer, ForeignKey('action_items.id')),
    Column('tag_id', Integer, ForeignKey('tags.id'))
)


class TermDB(Base):
    __tablename__ = "terms"
    
    id = Column(Integer, primary_key=True, index=True)
    term = Column(String, index=True, nullable=False)
    reading = Column(String, nullable=True)
    definition = Column(Text, nullable=True)
    term_type = Column(String, nullable=False)
    source_document = Column(String, nullable=True)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    

class TranscriptionDB(Base):
    __tablename__ = "transcriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String, nullable=False)
    original_text = Column(Text, nullable=False)
    corrected_text = Column(Text, nullable=False)
    segments = Column(Text, nullable=False)  # JSON
    duration = Column(Float, nullable=False)
    language = Column(String, default="ja")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    meeting_minutes = relationship("MeetingMinutesDB", back_populates="transcription")
    

class ActionItemDB(Base):
    __tablename__ = "action_items"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    assignee = Column(String, nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    priority = Column(String, nullable=False)
    status = Column(String, default="pending")
    source_segment = Column(Text, nullable=True)  # JSON
    confidence = Column(Float, default=1.0)
    meeting_minutes_id = Column(Integer, ForeignKey('meeting_minutes.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    meeting_minutes = relationship("MeetingMinutesDB", back_populates="action_items")
    tags = relationship("TagDB", secondary=action_item_tags, back_populates="action_items")
    

class MeetingMinutesDB(Base):
    __tablename__ = "meeting_minutes"
    
    id = Column(Integer, primary_key=True, index=True)
    meeting_title = Column(String, nullable=False)
    meeting_date = Column(DateTime(timezone=True), nullable=False)
    participants = Column(Text, nullable=False)  # JSON
    summary = Column(Text, nullable=False)
    transcription_id = Column(Integer, ForeignKey('transcriptions.id'))
    key_decisions = Column(Text, nullable=False)  # JSON
    next_steps = Column(Text, nullable=False)  # JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    transcription = relationship("TranscriptionDB", back_populates="meeting_minutes")
    action_items = relationship("ActionItemDB", back_populates="meeting_minutes")
    

class TagDB(Base):
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    category = Column(String, nullable=False)
    color = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    
    action_items = relationship("ActionItemDB", secondary=action_item_tags, back_populates="tags")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)