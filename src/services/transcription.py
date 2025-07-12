import whisper
import torch
from pathlib import Path
from typing import List, Optional, Dict, Any
import numpy as np
import logging
import json
from datetime import datetime
from ..core.models import TranscriptionSegment, TranscriptionResult
from ..core.database import TranscriptionDB, get_db
from ..core.config import settings
from .vector_search import TermCorrector, VectorSearchEngine
from sqlalchemy.orm import Session
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class WhisperTranscriber:
    def __init__(self):
        self.model = None
        self.device = settings.whisper_device
        self.model_name = settings.whisper_model
        self.vector_engine = VectorSearchEngine()
        self.term_corrector = TermCorrector(self.vector_engine)
        self.executor = ThreadPoolExecutor(max_workers=2)
        
    def load_model(self):
        if self.model is None:
            logger.info(f"Loading Whisper model: {self.model_name}")
            self.model = whisper.load_model(self.model_name, device=self.device)
            logger.info("Model loaded successfully")
            
    def transcribe_audio(self, audio_path: Path, language: str = "ja") -> Dict[str, Any]:
        self.load_model()
        
        logger.info(f"Transcribing audio: {audio_path}")
        
        result = self.model.transcribe(
            str(audio_path),
            language=language,
            task="transcribe",
            verbose=False,
            temperature=0.0,
            compression_ratio_threshold=2.4,
            logprob_threshold=-1.0,
            no_speech_threshold=0.6,
            condition_on_previous_text=True,
            initial_prompt="これは建設現場での会議の音声です。専門用語に注意してください。"
        )
        
        return result
    
    def process_segments(self, segments: List[Dict], apply_correction: bool = True) -> List[TranscriptionSegment]:
        processed_segments = []
        
        for segment in segments:
            text = segment["text"].strip()
            
            if apply_correction:
                corrected_text, corrections = self.term_corrector.correct_text(text)
            else:
                corrected_text = text
                corrections = []
                
            processed_segment = TranscriptionSegment(
                text=text,
                corrected_text=corrected_text,
                start_time=segment["start"],
                end_time=segment["end"],
                confidence=1.0 - segment.get("avg_logprob", 0),
                speaker=None
            )
            
            processed_segments.append(processed_segment)
            
        return processed_segments
    
    def merge_segments(self, segments: List[TranscriptionSegment], max_gap: float = 2.0) -> List[TranscriptionSegment]:
        if not segments:
            return []
            
        merged = []
        current = segments[0]
        
        for next_segment in segments[1:]:
            if next_segment.start_time - current.end_time <= max_gap:
                current = TranscriptionSegment(
                    text=current.text + " " + next_segment.text,
                    corrected_text=current.corrected_text + " " + next_segment.corrected_text,
                    start_time=current.start_time,
                    end_time=next_segment.end_time,
                    confidence=min(current.confidence, next_segment.confidence),
                    speaker=current.speaker
                )
            else:
                merged.append(current)
                current = next_segment
                
        merged.append(current)
        return merged
    
    async def transcribe_file(self, file_path: Path, apply_correction: bool = True) -> TranscriptionResult:
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self.transcribe_audio,
                file_path
            )
            
            segments = self.process_segments(result["segments"], apply_correction)
            
            segments = self.merge_segments(segments)
            
            original_text = " ".join([s.text for s in segments])
            corrected_text = " ".join([s.corrected_text for s in segments])
            
            transcription_result = TranscriptionResult(
                file_name=file_path.name,
                original_text=original_text,
                corrected_text=corrected_text,
                segments=segments,
                duration=result.get("duration", 0),
                language=result.get("language", "ja")
            )
            
            return transcription_result
            
        except Exception as e:
            logger.error(f"Error transcribing file {file_path}: {e}")
            raise
            
    def save_transcription(self, transcription: TranscriptionResult, db: Session) -> int:
        segments_json = json.dumps([s.dict() for s in transcription.segments], ensure_ascii=False)
        
        db_transcription = TranscriptionDB(
            file_name=transcription.file_name,
            original_text=transcription.original_text,
            corrected_text=transcription.corrected_text,
            segments=segments_json,
            duration=transcription.duration,
            language=transcription.language
        )
        
        db.add(db_transcription)
        db.commit()
        db.refresh(db_transcription)
        
        return db_transcription.id
    
    def get_transcription(self, transcription_id: int, db: Session) -> Optional[TranscriptionResult]:
        db_transcription = db.query(TranscriptionDB).filter(TranscriptionDB.id == transcription_id).first()
        
        if not db_transcription:
            return None
            
        segments = [TranscriptionSegment(**s) for s in json.loads(db_transcription.segments)]
        
        return TranscriptionResult(
            id=db_transcription.id,
            file_name=db_transcription.file_name,
            original_text=db_transcription.original_text,
            corrected_text=db_transcription.corrected_text,
            segments=segments,
            duration=db_transcription.duration,
            language=db_transcription.language,
            created_at=db_transcription.created_at
        )
    
    def identify_speakers(self, segments: List[TranscriptionSegment]) -> List[TranscriptionSegment]:
        updated_segments = []
        
        current_speaker = "Speaker 1"
        speaker_count = 1
        last_end_time = 0
        
        for segment in segments:
            if segment.start_time - last_end_time > 3.0:
                speaker_count += 1
                current_speaker = f"Speaker {speaker_count}"
                
            segment.speaker = current_speaker
            updated_segments.append(segment)
            last_end_time = segment.end_time
            
        return updated_segments
    
    def extract_key_phrases(self, text: str, min_length: int = 3) -> List[str]:
        terms_in_context = self.term_corrector.get_terms_in_context(text)
        
        key_phrases = []
        for term_info in terms_in_context:
            if term_info["confidence"] >= 0.8:
                key_phrases.append(term_info["term"])
                
        return list(set(key_phrases))


class RealTimeTranscriber:
    def __init__(self, transcriber: WhisperTranscriber):
        self.transcriber = transcriber
        self.buffer = []
        self.buffer_duration = 5.0
        
    async def process_audio_chunk(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> Optional[str]:
        chunk_duration = len(audio_chunk) / sample_rate
        
        self.buffer.append(audio_chunk)
        
        total_duration = sum(len(chunk) / sample_rate for chunk in self.buffer)
        
        if total_duration >= self.buffer_duration:
            combined_audio = np.concatenate(self.buffer)
            
            temp_file = Path("/tmp/temp_audio.wav")
            import soundfile as sf
            sf.write(temp_file, combined_audio, sample_rate)
            
            result = await self.transcriber.transcribe_file(temp_file, apply_correction=True)
            
            self.buffer = []
            
            temp_file.unlink()
            
            return result.corrected_text
            
        return None