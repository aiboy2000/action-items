import pytest
from unittest.mock import Mock, patch
from src.services.tagging import SmartTagger
from src.core.models import ActionItem, ActionItemPriority, ActionItemStatus
from datetime import datetime, timedelta


class TestSmartTagger:
    
    @pytest.fixture
    def tagger(self):
        return SmartTagger()
    
    def test_extract_tags(self, tagger):
        action_item = ActionItem(
            title="安全管理の徹底について",
            description="クレーン作業時の安全確認を強化する。緊急対応が必要。",
            assignee="山田さん",
            due_date=datetime.now() + timedelta(days=3),
            priority=ActionItemPriority.HIGH,
            status=ActionItemStatus.PENDING,
            confidence=0.9
        )
        
        tags = tagger.extract_tags(action_item)
        
        # Should include safety tag
        assert "安全" in tags
        
        # Should include urgency tag
        assert "緊急" in tags
        
        # Should include priority tag
        assert "重要度:高" in tags
        
        # Should include due date tag
        assert "期限あり" in tags
        
        # Should include assignee tag
        assert "担当:山田さん" in tags
        
        # Should not exceed 10 tags
        assert len(tags) <= 10
    
    def test_extract_phase_tags(self, tagger):
        # Test foundation phase
        text = "基礎工事の杭打ち作業について"
        tags = tagger._extract_phase_tags(text)
        assert "基礎工事" in tags
        
        # Test structure phase
        text = "鉄筋コンクリート躯体の施工"
        tags = tagger._extract_phase_tags(text)
        assert "躯体工事" in tags
        
        # Test finishing phase
        text = "外装の塗装作業を開始"
        tags = tagger._extract_phase_tags(text)
        assert "仕上工事" in tags
        
        # Test equipment phase
        text = "電気設備の配線工事"
        tags = tagger._extract_phase_tags(text)
        assert "設備工事" in tags
    
    def test_get_tag_info(self, tagger):
        # Test known tag
        info = tagger._get_tag_info("安全")
        assert info["category"] == "safety"
        assert info["color"] == "#FF0000"
        
        # Test assignee tag
        info = tagger._get_tag_info("担当:田中さん")
        assert info["category"] == "assignee"
        assert "田中さん" in info["description"]
        
        # Test priority tag
        info = tagger._get_tag_info("重要度:高")
        assert info["category"] == "priority"
        
        # Test phase tag
        info = tagger._get_tag_info("基礎工事")
        assert info["category"] == "phase"
        
        # Test unknown tag
        info = tagger._get_tag_info("その他のタグ")
        assert info["category"] == "other"
    
    @patch('src.services.tagging.get_db')
    def test_create_or_get_tags(self, mock_get_db, tagger):
        mock_db = Mock()
        
        # Mock existing tag
        existing_tag = Mock(name="安全", category="safety", color="#FF0000")
        mock_db.query().filter().first.side_effect = [existing_tag, None]
        
        tag_names = ["安全", "新しいタグ"]
        tags = tagger.create_or_get_tags(tag_names, mock_db)
        
        # Should return existing tag without creating
        assert len(tags) == 2
        assert tags[0] == existing_tag
        
        # Should create new tag
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()
    
    @patch('src.services.tagging.get_db')
    def test_find_related_items(self, mock_get_db, tagger):
        mock_db = Mock()
        
        # Mock action item with tags
        tag1 = Mock(id=1, name="安全")
        tag2 = Mock(id=2, name="緊急")
        mock_item = Mock(id=1, tags=[tag1, tag2])
        
        # Mock related items
        related_item1 = Mock(id=2, title="関連アイテム1")
        related_item2 = Mock(id=3, title="関連アイテム2")
        
        mock_db.query().filter().first.return_value = mock_item
        mock_db.query().join().filter().distinct().limit().all.return_value = [
            related_item1, related_item2
        ]
        
        related = tagger.find_related_items(1, mock_db, limit=5)
        
        assert len(related) == 2
        assert related[0] == related_item1
        assert related[1] == related_item2
    
    @patch('src.services.tagging.get_db')
    def test_search_by_tags(self, mock_get_db, tagger):
        mock_db = Mock()
        
        # Mock search results
        item1 = Mock(id=1, title="アイテム1")
        item2 = Mock(id=2, title="アイテム2")
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.distinct().all.return_value = [item1, item2]
        mock_db.query().join.return_value = mock_query
        
        results = tagger.search_by_tags(["安全", "緊急"], mock_db)
        
        assert len(results) == 2
        assert results[0] == item1
        assert results[1] == item2
        
        # Verify filter was called for each tag
        assert mock_query.filter.call_count == 2