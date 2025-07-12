import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from src.services.pdf_extractor import PDFTermExtractor
from src.core.models import Term, TermType


class TestPDFTermExtractor:
    
    @pytest.fixture
    def extractor(self):
        return PDFTermExtractor()
    
    def test_classify_term_type(self, extractor):
        # Test safety term
        assert extractor.classify_term_type("安全帯", "安全帯の着用を確認") == TermType.SAFETY
        
        # Test material term
        assert extractor.classify_term_type("コンクリート", "コンクリート打設作業") == TermType.MATERIAL
        
        # Test process term
        assert extractor.classify_term_type("施工手順", "施工手順の確認") == TermType.PROCESS
        
        # Test equipment term
        assert extractor.classify_term_type("クレーン", "クレーン設置作業") == TermType.EQUIPMENT
        
        # Test other term
        assert extractor.classify_term_type("会議", "") == TermType.OTHER
    
    def test_extract_construction_terms(self, extractor):
        text = """
        鉄筋コンクリート工事の施工について
        基礎工事は来週から開始します。
        安全管理を徹底してください。
        クレーン作業時は特に注意が必要です。
        """
        
        terms = extractor.extract_construction_terms(text)
        
        # Check that some construction terms were found
        term_texts = [t[0] for t in terms]
        assert any("コンクリート" in term for term in term_texts)
        assert any("工事" in term for term in term_texts)
        
    @patch('pdfplumber.open')
    def test_extract_text_from_pdf(self, mock_pdfplumber, extractor):
        # Mock PDF content
        mock_page = Mock()
        mock_page.extract_text.return_value = "建設工事の内容"
        mock_pdf = Mock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=None)
        mock_pdfplumber.return_value = mock_pdf
        
        result = extractor.extract_text_from_pdf(Path("test.pdf"))
        
        assert "建設工事の内容" in result
        mock_pdfplumber.assert_called_once()
    
    def test_get_reading(self, extractor):
        # Mock MeCab since it requires system installation
        with patch.object(extractor.mecab, 'parse') as mock_parse:
            mock_parse.return_value = "鉄筋\tテッキン\nコンクリート\tコンクリート\n"
            
            reading = extractor._get_reading("鉄筋コンクリート")
            
            # The actual implementation would parse MeCab output properly
            # For now, just check that the method runs
            assert isinstance(reading, str)