import numpy as np
import faiss
import pickle
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import logging
from sentence_transformers import SentenceTransformer
from ..core.database import TermDB, get_db
from ..core.config import settings
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class VectorSearchEngine:
    def __init__(self, model_name: str = "sonoisa/sentence-bert-base-ja-mean-tokens-v2"):
        self.model = SentenceTransformer(model_name)
        self.index: Optional[faiss.IndexFlatL2] = None
        self.id_to_term: Dict[int, str] = {}
        self.term_to_id: Dict[str, int] = {}
        self.index_path = Path(settings.faiss_index_path)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        
    def create_embeddings(self, texts: List[str]) -> np.ndarray:
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.astype('float32')
    
    def build_index_from_db(self, db: Session):
        terms = db.query(TermDB).all()
        
        if not terms:
            logger.warning("No terms found in database")
            return
            
        term_texts = [term.term for term in terms]
        term_ids = [term.id for term in terms]
        
        embeddings = self.create_embeddings(term_texts)
        
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings)
        
        self.id_to_term = {i: term_texts[i] for i in range(len(term_texts))}
        self.term_to_id = {term_texts[i]: term_ids[i] for i in range(len(term_texts))}
        
        self.save_index()
        
        logger.info(f"Built index with {len(terms)} terms")
        
    def save_index(self):
        if self.index is None:
            logger.error("No index to save")
            return
            
        faiss.write_index(self.index, str(self.index_path / "terms.index"))
        
        with open(self.index_path / "mappings.pkl", "wb") as f:
            pickle.dump({
                "id_to_term": self.id_to_term,
                "term_to_id": self.term_to_id
            }, f)
            
        logger.info("Index saved successfully")
        
    def load_index(self) -> bool:
        index_file = self.index_path / "terms.index"
        mappings_file = self.index_path / "mappings.pkl"
        
        if not index_file.exists() or not mappings_file.exists():
            logger.warning("Index files not found")
            return False
            
        try:
            self.index = faiss.read_index(str(index_file))
            
            with open(mappings_file, "rb") as f:
                mappings = pickle.load(f)
                self.id_to_term = mappings["id_to_term"]
                self.term_to_id = mappings["term_to_id"]
                
            logger.info("Index loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error loading index: {e}")
            return False
            
    def search(self, query: str, k: int = 10, threshold: float = 0.8) -> List[Tuple[str, float, int]]:
        if self.index is None:
            if not self.load_index():
                logger.error("No index available for search")
                return []
                
        query_embedding = self.create_embeddings([query])
        
        distances, indices = self.index.search(query_embedding, k)
        
        results = []
        for i in range(len(indices[0])):
            idx = indices[0][i]
            distance = distances[0][i]
            
            if idx == -1:
                continue
                
            similarity = 1 / (1 + distance)
            
            if similarity >= threshold:
                term = self.id_to_term.get(idx, "")
                db_id = self.term_to_id.get(term, -1)
                results.append((term, similarity, db_id))
                
        return results
    
    def find_similar_terms(self, term: str, k: int = 5) -> List[Tuple[str, float]]:
        results = self.search(term, k=k+1, threshold=0.0)
        
        filtered_results = [(t, s) for t, s, _ in results if t.lower() != term.lower()]
        
        return filtered_results[:k]
    
    def update_single_term(self, term: TermDB):
        if not self.load_index():
            db = next(get_db())
            self.build_index_from_db(db)
            return
            
        term_embedding = self.create_embeddings([term.term])
        
        new_idx = len(self.id_to_term)
        self.index.add(term_embedding)
        self.id_to_term[new_idx] = term.term
        self.term_to_id[term.term] = term.id
        
        self.save_index()


class TermCorrector:
    def __init__(self, vector_engine: VectorSearchEngine):
        self.vector_engine = vector_engine
        self.db = next(get_db())
        
    def correct_text(self, text: str, confidence_threshold: float = 0.85) -> Tuple[str, List[Dict]]:
        words = text.split()
        corrected_words = []
        corrections = []
        
        for i, word in enumerate(words):
            if len(word) < 2:
                corrected_words.append(word)
                continue
                
            search_results = self.vector_engine.search(word, k=1, threshold=confidence_threshold)
            
            if search_results:
                best_match, similarity, db_id = search_results[0]
                
                if best_match.lower() != word.lower() and similarity >= confidence_threshold:
                    corrected_words.append(best_match)
                    corrections.append({
                        "original": word,
                        "corrected": best_match,
                        "confidence": similarity,
                        "position": i
                    })
                else:
                    corrected_words.append(word)
            else:
                corrected_words.append(word)
                
        corrected_text = " ".join(corrected_words)
        return corrected_text, corrections
    
    def get_terms_in_context(self, text: str, window_size: int = 50) -> List[Dict]:
        found_terms = []
        
        all_terms = self.db.query(TermDB).filter(TermDB.confidence >= 0.7).all()
        
        for term in all_terms:
            term_text = term.term.lower()
            text_lower = text.lower()
            
            start = 0
            while True:
                pos = text_lower.find(term_text, start)
                if pos == -1:
                    break
                    
                context_start = max(0, pos - window_size)
                context_end = min(len(text), pos + len(term_text) + window_size)
                context = text[context_start:context_end]
                
                found_terms.append({
                    "term": term.term,
                    "type": term.term_type,
                    "position": pos,
                    "context": context,
                    "confidence": term.confidence
                })
                
                start = pos + 1
                
        return found_terms