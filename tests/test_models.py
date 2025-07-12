import pytest
from datetime import datetime
from src.core.models import (
    Term, TermType, TranscriptionSegment, TranscriptionResult,
    ActionItem, ActionItemPriority, ActionItemStatus, MeetingMinutes
)


def test_term_model():
    term = Term(
        term="鉄筋コンクリート",
        reading="テッキンコンクリート",
        definition="鉄筋で補強されたコンクリート",
        term_type=TermType.MATERIAL,
        source_document="construction_manual.pdf",
        confidence=0.95
    )
    
    assert term.term == "鉄筋コンクリート"
    assert term.term_type == TermType.MATERIAL
    assert term.confidence == 0.95
    assert 0.0 <= term.confidence <= 1.0


def test_transcription_segment():
    segment = TranscriptionSegment(
        text="本日の議題は工程の確認です",
        start_time=0.0,
        end_time=3.5,
        confidence=0.92,
        speaker="Speaker 1",
        corrected_text="本日の議題は工程の確認です"
    )
    
    assert segment.start_time == 0.0
    assert segment.end_time == 3.5
    assert segment.confidence == 0.92


def test_action_item():
    action_item = ActionItem(
        title="設計図面の修正",
        description="3階部分の設計図面を修正して再提出する",
        assignee="田中さん",
        due_date=datetime(2024, 2, 1),
        priority=ActionItemPriority.HIGH,
        status=ActionItemStatus.PENDING,
        tags=["設計変更", "緊急"],
        confidence=0.85
    )
    
    assert action_item.priority == ActionItemPriority.HIGH
    assert action_item.status == ActionItemStatus.PENDING
    assert len(action_item.tags) == 2
    assert "緊急" in action_item.tags


def test_meeting_minutes():
    action_items = [
        ActionItem(
            title="資材発注",
            description="次週分の資材を発注",
            priority=ActionItemPriority.MEDIUM,
            status=ActionItemStatus.PENDING,
            confidence=0.9
        )
    ]
    
    minutes = MeetingMinutes(
        meeting_title="第5回工程会議",
        meeting_date=datetime(2024, 1, 15),
        participants=["田中", "山田", "佐藤"],
        summary="工程の進捗確認と今後の計画について議論",
        transcription_id=1,
        action_items=action_items,
        key_decisions=["工期を1週間延長することを決定"],
        next_steps=["来週の月曜日に再度確認"]
    )
    
    assert minutes.meeting_title == "第5回工程会議"
    assert len(minutes.participants) == 3
    assert len(minutes.action_items) == 1
    assert minutes.action_items[0].title == "資材発注"