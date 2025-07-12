from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path
import shutil
from ...core.database import get_db
from ...core.models import Term, TermType
from ...services.pdf_extractor import PDFTermExtractor
from ...services.vector_search import VectorSearchEngine

router = APIRouter()


@router.post("/extract-from-pdf")
async def extract_terms_from_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
    temp_file = Path(f"/tmp/{file.filename}")
    with temp_file.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    extractor = PDFTermExtractor()
    
    def process_pdf():
        try:
            terms = extractor.extract_terms_from_pdf(temp_file, file.filename)
            extractor.save_terms_to_db(terms, db)
            
            vector_engine = VectorSearchEngine()
            vector_engine.build_index_from_db(db)
            
            temp_file.unlink()
        except Exception as e:
            print(f"Error processing PDF: {e}")
            
    background_tasks.add_task(process_pdf)
    
    return {"message": "PDF processing started", "filename": file.filename}


@router.post("/process-directory")
async def process_pdf_directory(
    directory_path: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    directory = Path(directory_path)
    if not directory.exists() or not directory.is_dir():
        raise HTTPException(status_code=400, detail="Invalid directory path")
        
    extractor = PDFTermExtractor()
    
    def process_directory():
        results = extractor.process_pdf_directory(directory)
        
        vector_engine = VectorSearchEngine()
        vector_engine.build_index_from_db(db)
        
        return results
        
    background_tasks.add_task(process_directory)
    
    return {"message": "Directory processing started", "path": directory_path}


@router.get("/search")
async def search_terms(
    query: str,
    limit: int = 10,
    threshold: float = 0.8
):
    vector_engine = VectorSearchEngine()
    results = vector_engine.search(query, k=limit, threshold=threshold)
    
    return {
        "query": query,
        "results": [
            {
                "term": term,
                "similarity": similarity,
                "id": db_id
            }
            for term, similarity, db_id in results
        ]
    }


@router.get("/similar/{term}")
async def find_similar_terms(
    term: str,
    limit: int = 5
):
    vector_engine = VectorSearchEngine()
    results = vector_engine.find_similar_terms(term, k=limit)
    
    return {
        "term": term,
        "similar_terms": [
            {
                "term": similar_term,
                "similarity": similarity
            }
            for similar_term, similarity in results
        ]
    }


@router.post("/rebuild-index")
async def rebuild_vector_index(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    def rebuild():
        vector_engine = VectorSearchEngine()
        vector_engine.build_index_from_db(db)
        
    background_tasks.add_task(rebuild)
    
    return {"message": "Index rebuild started"}