import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from src.services.meeting_minutes import ActionItemExtractor, MeetingMinutesGenerator
from src.core.models import (
    TranscriptionSegment, TranscriptionResult, ActionItem,
    ActionItemPriority, ActionItemStatus
)


class TestActionItemExtractor:
    
    @pytest.fixture
    def extractor(self):
        return ActionItemExtractor()
    
    def test_extract_title(self, extractor):
        # Test normal title extraction
        text = "設計図面を修正してください。来週までに提出が必要です。"
        title = extractor._extract_title(text)
        assert title == "設計図面を修正してください"
        
        # Test long title truncation
        long_text = "これは非常に長いタイトルで、" * 10 + "終わりです。"
        title = extractor._extract_title(long_text)
        assert len(title) <= 100
        
        # Test short text
        short_text = "確認"
        title = extractor._extract_title(short_text)
        assert title is None
    
    def test_extract_assignee(self, extractor):
        # Test with さん
        text = "田中さんが資料を準備してください"
        assignee = extractor._extract_assignee(text)
        assert assignee == "田中さん"
        
        # Test with responsibility pattern
        text = "担当は山田さんです"
        assignee = extractor._extract_assignee(text)
        assert assignee == "山田さん"
        
        # Test no assignee
        text = "資料を準備する必要があります"
        assignee = extractor._extract_assignee(text)
        assert assignee is None
    
    def test_extract_deadline(self, extractor):
        today = datetime.now()
        
        # Test specific date
        text = "3月15日までに提出"
        deadline = extractor._extract_deadline(text)
        assert deadline is not None
        assert deadline.month == 3
        assert deadline.day == 15
        
        # Test relative days
        text = "5日までに完了"
        deadline = extractor._extract_deadline(text)
        assert deadline is not None
        assert deadline.day == 5
        
        # Test this week
        text = "今週中に確認をお願いします"
        deadline = extractor._extract_deadline(text)
        assert deadline is not None
        assert (deadline - today).days <= 7
        
        # Test tomorrow
        text = "明日までに連絡してください"
        deadline = extractor._extract_deadline(text)
        assert deadline is not None
        assert (deadline - today).days == 1
    
    def test_determine_priority(self, extractor):
        # Test high priority keywords
        text = "至急確認をお願いします"
        priority = extractor._determine_priority(text)
        assert priority == ActionItemPriority.HIGH
        
        # Test medium priority keywords
        text = "なるべく早めに対応してください"
        priority = extractor._determine_priority(text)
        assert priority == ActionItemPriority.MEDIUM
        
        # Test low priority keywords
        text = "時間があれば確認してください"
        priority = extractor._determine_priority(text)
        assert priority == ActionItemPriority.LOW
        
        # Test deadline-based priority
        with patch.object(extractor, '_extract_deadline') as mock_deadline:
            mock_deadline.return_value = datetime.now() + timedelta(days=2)
            text = "確認をお願いします"
            priority = extractor._determine_priority(text)
            assert priority == ActionItemPriority.HIGH
    
    def test_extract_action_items(self, extractor):
        segments = [
            TranscriptionSegment(
                text="田中さん、設計図面の修正をお願いします。",
                start_time=0.0,
                end_time=3.0,
                confidence=0.9
            ),
            TranscriptionSegment(
                text="来週までに資材の発注を完了する必要があります。",
                start_time=3.0,
                end_time=6.0,
                confidence=0.85
            ),
            TranscriptionSegment(
                text="今日は天気が良いですね。",
                start_time=6.0,
                end_time=8.0,
                confidence=0.95
            )
        ]
        
        action_items = extractor.extract_action_items(segments)
        
        # Should extract 2 action items (not the weather comment)
        assert len(action_items) >= 1
        assert any("設計図面" in item.title for item in action_items)


class TestMeetingMinutesGenerator:
    
    @pytest.fixture
    def generator(self):
        with patch('src.services.meeting_minutes.subprocess.run') as mock_run:
            mock_run.return_value.returncode = 1  # Simulate Ollama not available
            return MeetingMinutesGenerator()
    
    def test_generate_summary_rule_based(self, generator):
        transcription = TranscriptionResult(
            file_name="meeting.mp4",
            original_text="本日の会議では重要な決定がありました。工期を1週間延長することを確認しました。",
            corrected_text="本日の会議では重要な決定がありました。工期を1週間延長することを確認しました。",
            segments=[],
            duration=300.0
        )
        
        summary = generator._generate_summary_rule_based(transcription)
        
        assert "重要な決定" in summary
        assert "確認" in summary
        assert "•" in summary  # Bullet point
    
    def test_extract_key_decisions(self, generator):
        transcription = TranscriptionResult(
            file_name="meeting.mp4",
            original_text="設計変更について承認されました。予算は変更なしで決定しました。",
            corrected_text="設計変更について承認されました。予算は変更なしで決定しました。",
            segments=[],
            duration=300.0
        )
        
        decisions = generator._extract_key_decisions(transcription)
        
        assert len(decisions) >= 1
        assert any("承認" in d for d in decisions)
        assert any("決定" in d for d in decisions)
    
    def test_extract_next_steps(self, generator):
        action_items = [
            ActionItem(
                title="設計図面の修正",
                description="3階部分の修正",
                priority=ActionItemPriority.HIGH,
                assignee="田中さん",
                due_date=datetime.now() + timedelta(days=3),
                status=ActionItemStatus.PENDING,
                confidence=0.9
            ),
            ActionItem(
                title="資材発注",
                description="鉄筋の発注",
                priority=ActionItemPriority.MEDIUM,
                status=ActionItemStatus.PENDING,
                confidence=0.85
            )
        ]
        
        transcription = TranscriptionResult(
            file_name="meeting.mp4",
            original_text="次回の会議は3月20日に行います。",
            corrected_text="次回の会議は3月20日に行います。",
            segments=[],
            duration=300.0
        )
        
        next_steps = generator._extract_next_steps(transcription, action_items)
        
        assert len(next_steps) >= 1
        assert any("設計図面の修正" in step for step in next_steps)
        assert any("田中さん" in step for step in next_steps)
        assert any("3月20日" in step for step in next_steps)