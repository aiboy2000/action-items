import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from src.services.vector_search import VectorSearchEngine, TermCorrector


class TestVectorSearchEngine:
    
    @pytest.fixture
    def vector_engine(self):
        with patch('src.services.vector_search.SentenceTransformer'):
            return VectorSearchEngine()
    
    def test_create_embeddings(self, vector_engine):
        # Mock the model's encode method
        mock_embeddings = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
        vector_engine.model.encode = Mock(return_value=mock_embeddings)
        
        texts = ["コンクリート", "鉄筋"]
        embeddings = vector_engine.create_embeddings(texts)
        
        assert embeddings.shape == (2, 3)
        assert embeddings.dtype == np.float32
        vector_engine.model.encode.assert_called_once_with(texts, convert_to_numpy=True)
    
    @patch('src.services.vector_search.faiss')
    def test_build_index_from_db(self, mock_faiss, vector_engine):
        # Mock database terms
        mock_db = Mock()
        mock_terms = [
            Mock(id=1, term="コンクリート"),
            Mock(id=2, term="鉄筋")
        ]
        mock_db.query().all.return_value = mock_terms
        
        # Mock embeddings
        mock_embeddings = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)
        vector_engine.model.encode = Mock(return_value=mock_embeddings)
        
        # Mock FAISS index
        mock_index = Mock()
        mock_faiss.IndexFlatL2.return_value = mock_index
        
        vector_engine.build_index_from_db(mock_db)
        
        assert vector_engine.index is not None
        assert len(vector_engine.id_to_term) == 2
        assert vector_engine.id_to_term[0] == "コンクリート"
        assert vector_engine.term_to_id["コンクリート"] == 1
    
    def test_search_without_index(self, vector_engine):
        vector_engine.index = None
        vector_engine.load_index = Mock(return_value=False)
        
        results = vector_engine.search("test query")
        
        assert results == []
        vector_engine.load_index.assert_called_once()


class TestTermCorrector:
    
    @pytest.fixture
    def term_corrector(self):
        with patch('src.services.vector_search.VectorSearchEngine'):
            with patch('src.services.vector_search.get_db'):
                mock_engine = Mock()
                return TermCorrector(mock_engine)
    
    def test_correct_text(self, term_corrector):
        # Mock search results
        term_corrector.vector_engine.search = Mock(
            side_effect=[
                [("コンクリート", 0.9, 1)],  # First word correction
                [],  # Second word no correction
                [("施工", 0.85, 2)]  # Third word correction
            ]
        )
        
        text = "コンクリト の せこう"
        corrected_text, corrections = term_corrector.correct_text(text)
        
        assert corrected_text == "コンクリート の 施工"
        assert len(corrections) == 2
        assert corrections[0]["original"] == "コンクリト"
        assert corrections[0]["corrected"] == "コンクリート"
        assert corrections[1]["original"] == "せこう"
        assert corrections[1]["corrected"] == "施工"
    
    def test_get_terms_in_context(self, term_corrector):
        # Mock database terms
        mock_terms = [
            Mock(term="コンクリート", term_type="material", confidence=0.9),
            Mock(term="鉄筋", term_type="material", confidence=0.8)
        ]
        term_corrector.db.query().filter().all.return_value = mock_terms
        
        text = "鉄筋コンクリート工事では、まず鉄筋を配置してからコンクリートを打設します。"
        
        found_terms = term_corrector.get_terms_in_context(text)
        
        # Should find both terms
        assert len(found_terms) >= 2
        term_names = [t["term"] for t in found_terms]
        assert "コンクリート" in term_names
        assert "鉄筋" in term_names