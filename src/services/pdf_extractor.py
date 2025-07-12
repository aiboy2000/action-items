import re
from typing import List, Dict, Tuple
import PyPDF2
import pdfplumber
from pathlib import Path
import logging
from ..core.models import Term, TermType
from ..core.database import TermDB, get_db
from sqlalchemy.orm import Session
import MeCab
from collections import Counter

logger = logging.getLogger(__name__)


class PDFTermExtractor:
    def __init__(self):
        self.mecab = MeCab.Tagger()
        self.construction_patterns = [
            r'[ァ-ヴー]+(?:工事|作業|施工|建設|建築)',
            r'(?:鉄筋|鉄骨|コンクリート|アスファルト|基礎|躯体|仕上げ|防水|塗装|電気|配管|空調|設備)',
            r'(?:図面|設計|施工図|仕様書|工程表|安全)',
            r'[0-9]+(?:mm|cm|m|kg|t|㎡|m2|m3|MPa|N)',
        ]
        
        self.term_types_keywords = {
            TermType.TECHNICAL: ['工法', '技術', '方法', '仕様', '規格', '基準'],
            TermType.MATERIAL: ['材料', '資材', '鋼材', 'コンクリート', 'セメント', '骨材'],
            TermType.PROCESS: ['工程', '手順', '作業', '施工', '検査', '試験'],
            TermType.SAFETY: ['安全', '危険', '保護', '防護', '事故', '災害'],
            TermType.EQUIPMENT: ['機械', '設備', '工具', '器具', 'クレーン', '重機'],
        }
        
    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        text = ""
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            logger.warning(f"pdfplumber failed for {pdf_path}: {e}")
            
            try:
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
            except Exception as e2:
                logger.error(f"Both PDF extraction methods failed for {pdf_path}: {e2}")
                raise
                
        return text
    
    def classify_term_type(self, term: str, context: str = "") -> TermType:
        combined_text = f"{term} {context}".lower()
        
        type_scores = {}
        for term_type, keywords in self.term_types_keywords.items():
            score = sum(1 for keyword in keywords if keyword in combined_text)
            type_scores[term_type] = score
            
        if max(type_scores.values()) > 0:
            return max(type_scores, key=type_scores.get)
        return TermType.OTHER
    
    def extract_construction_terms(self, text: str) -> List[Tuple[str, float]]:
        terms = []
        
        lines = text.split('\n')
        for line in lines:
            for pattern in self.construction_patterns:
                matches = re.findall(pattern, line)
                for match in matches:
                    if len(match) >= 2:
                        terms.append((match, 0.8))
        
        parsed = self.mecab.parse(text)
        lines = parsed.split('\n')
        
        compound_noun = []
        for line in lines:
            if '\t' not in line:
                continue
                
            surface, features = line.split('\t')
            feature_list = features.split(',')
            
            if feature_list[0] == '名詞':
                if feature_list[1] in ['固有名詞', '一般', 'サ変接続']:
                    compound_noun.append(surface)
                else:
                    if len(compound_noun) >= 2:
                        term = ''.join(compound_noun)
                        if len(term) >= 3:
                            terms.append((term, 0.6))
                    compound_noun = []
            else:
                if len(compound_noun) >= 2:
                    term = ''.join(compound_noun)
                    if len(term) >= 3:
                        terms.append((term, 0.6))
                compound_noun = []
        
        term_counter = Counter([t[0] for t in terms])
        filtered_terms = []
        for term, confidence in terms:
            if term_counter[term] >= 2:
                filtered_terms.append((term, min(confidence * 1.2, 1.0)))
            elif len(term) >= 4:
                filtered_terms.append((term, confidence))
                
        return list(set(filtered_terms))
    
    def extract_terms_from_pdf(self, pdf_path: Path, source_name: str = None) -> List[Term]:
        if source_name is None:
            source_name = pdf_path.name
            
        text = self.extract_text_from_pdf(pdf_path)
        raw_terms = self.extract_construction_terms(text)
        
        terms = []
        for term_text, confidence in raw_terms:
            term_type = self.classify_term_type(term_text, text[:500])
            
            reading = self._get_reading(term_text)
            
            term = Term(
                term=term_text,
                reading=reading,
                term_type=term_type,
                source_document=source_name,
                confidence=confidence
            )
            terms.append(term)
            
        return terms
    
    def _get_reading(self, text: str) -> str:
        parsed = self.mecab.parse(text)
        readings = []
        
        for line in parsed.split('\n'):
            if '\t' not in line:
                continue
            surface, features = line.split('\t')
            feature_list = features.split(',')
            
            if len(feature_list) >= 8 and feature_list[7] != '*':
                readings.append(feature_list[7])
            else:
                readings.append(surface)
                
        return ''.join(readings)
    
    def save_terms_to_db(self, terms: List[Term], db: Session):
        for term in terms:
            existing = db.query(TermDB).filter(TermDB.term == term.term).first()
            
            if existing:
                if term.confidence > existing.confidence:
                    existing.confidence = term.confidence
                    existing.source_document = term.source_document
                    existing.term_type = term.term_type.value
            else:
                db_term = TermDB(
                    term=term.term,
                    reading=term.reading,
                    definition=term.definition,
                    term_type=term.term_type.value,
                    source_document=term.source_document,
                    confidence=term.confidence
                )
                db.add(db_term)
                
        db.commit()
    
    def process_pdf_directory(self, directory: Path) -> Dict[str, int]:
        results = {
            "processed_files": 0,
            "extracted_terms": 0,
            "errors": []
        }
        
        pdf_files = list(directory.glob("*.pdf"))
        
        for pdf_file in pdf_files:
            try:
                logger.info(f"Processing {pdf_file.name}")
                terms = self.extract_terms_from_pdf(pdf_file)
                
                db = next(get_db())
                self.save_terms_to_db(terms, db)
                
                results["processed_files"] += 1
                results["extracted_terms"] += len(terms)
                
            except Exception as e:
                logger.error(f"Error processing {pdf_file.name}: {e}")
                results["errors"].append(f"{pdf_file.name}: {str(e)}")
                
        return results