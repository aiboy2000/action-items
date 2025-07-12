import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import logging
import json
from ..core.models import (
    ActionItem, ActionItemPriority, ActionItemStatus,
    MeetingMinutes, TranscriptionResult, TranscriptionSegment
)
from ..core.database import MeetingMinutesDB, ActionItemDB, get_db
from sqlalchemy.orm import Session
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class ActionItemExtractor:
    def __init__(self):
        self.action_patterns = [
            r'(?:〜すること|〜してください|〜お願いします|〜する必要があります)',
            r'(?:確認|検討|準備|作成|提出|連絡|調整|実施)(?:する|して|します)',
            r'(?:〜まで|までに)(?:〜|.*?)(?:する|完了|提出|準備)',
            r'(?:次回|来週|今週|明日|今日).*?(?:持参|準備|確認|提出)',
            r'(?:宿題|課題|タスク|TODO|やること)',
        ]
        
        self.priority_keywords = {
            ActionItemPriority.HIGH: ['至急', '緊急', '重要', '最優先', '早急', '即日', '本日中'],
            ActionItemPriority.MEDIUM: ['なるべく', '可能な限り', '優先', '今週中', '近日中'],
            ActionItemPriority.LOW: ['時間があれば', '余裕があれば', '後日', '将来的に']
        }
        
        self.deadline_patterns = [
            (r'(\d+)月(\d+)日', 'date'),
            (r'(\d+)日まで', 'relative_day'),
            (r'今週中', 'this_week'),
            (r'来週', 'next_week'),
            (r'今月中', 'this_month'),
            (r'来月', 'next_month'),
            (r'明日', 'tomorrow'),
            (r'本日中', 'today'),
        ]
        
    def extract_action_items(self, segments: List[TranscriptionSegment]) -> List[ActionItem]:
        action_items = []
        
        for segment in segments:
            text = segment.corrected_text or segment.text
            
            for pattern in self.action_patterns:
                if re.search(pattern, text):
                    action_item = self._create_action_item(segment, text)
                    if action_item:
                        action_items.append(action_item)
                        break
                        
        return self._merge_similar_items(action_items)
    
    def _create_action_item(self, segment: TranscriptionSegment, text: str) -> Optional[ActionItem]:
        title = self._extract_title(text)
        if not title:
            return None
            
        description = text
        assignee = self._extract_assignee(text)
        due_date = self._extract_deadline(text)
        priority = self._determine_priority(text)
        
        return ActionItem(
            title=title,
            description=description,
            assignee=assignee,
            due_date=due_date,
            priority=priority,
            source_segment=segment,
            confidence=segment.confidence
        )
    
    def _extract_title(self, text: str) -> Optional[str]:
        sentences = text.split('。')
        if not sentences:
            return None
            
        title = sentences[0].strip()
        
        if len(title) > 50:
            words = title.split('、')
            if words:
                title = words[0]
                
        if len(title) < 5:
            return None
            
        return title[:100]
    
    def _extract_assignee(self, text: str) -> Optional[str]:
        assignee_patterns = [
            r'(\w+)さん.*?(?:お願い|担当|確認)',
            r'(\w+)(?:さん)?.*?(?:が|は).*?(?:する|します)',
            r'(?:担当|責任者).*?(\w+)さん',
        ]
        
        for pattern in assignee_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1) + "さん"
                
        return None
    
    def _extract_deadline(self, text: str) -> Optional[datetime]:
        today = datetime.now()
        
        for pattern, pattern_type in self.deadline_patterns:
            match = re.search(pattern, text)
            if match:
                if pattern_type == 'date':
                    month = int(match.group(1))
                    day = int(match.group(2))
                    year = today.year
                    if month < today.month:
                        year += 1
                    try:
                        return datetime(year, month, day)
                    except ValueError:
                        continue
                        
                elif pattern_type == 'relative_day':
                    days = int(match.group(1))
                    return today + timedelta(days=days)
                    
                elif pattern_type == 'this_week':
                    days_until_friday = 4 - today.weekday()
                    if days_until_friday < 0:
                        days_until_friday += 7
                    return today + timedelta(days=days_until_friday)
                    
                elif pattern_type == 'next_week':
                    return today + timedelta(weeks=1)
                    
                elif pattern_type == 'this_month':
                    return datetime(today.year, today.month, 28)
                    
                elif pattern_type == 'next_month':
                    if today.month == 12:
                        return datetime(today.year + 1, 1, 28)
                    else:
                        return datetime(today.year, today.month + 1, 28)
                        
                elif pattern_type == 'tomorrow':
                    return today + timedelta(days=1)
                    
                elif pattern_type == 'today':
                    return today
                    
        return None
    
    def _determine_priority(self, text: str) -> ActionItemPriority:
        for priority, keywords in self.priority_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return priority
                    
        if self._extract_deadline(text):
            deadline = self._extract_deadline(text)
            if deadline:
                days_until = (deadline - datetime.now()).days
                if days_until <= 3:
                    return ActionItemPriority.HIGH
                elif days_until <= 7:
                    return ActionItemPriority.MEDIUM
                    
        return ActionItemPriority.MEDIUM
    
    def _merge_similar_items(self, items: List[ActionItem]) -> List[ActionItem]:
        if len(items) <= 1:
            return items
            
        merged = []
        used = set()
        
        for i, item1 in enumerate(items):
            if i in used:
                continue
                
            similar_items = [item1]
            
            for j, item2 in enumerate(items[i+1:], i+1):
                if j in used:
                    continue
                    
                if self._are_similar(item1.title, item2.title):
                    similar_items.append(item2)
                    used.add(j)
                    
            if len(similar_items) > 1:
                merged_item = self._merge_items(similar_items)
                merged.append(merged_item)
            else:
                merged.append(item1)
                
        return merged
    
    def _are_similar(self, text1: str, text2: str) -> bool:
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        if not union:
            return False
            
        similarity = len(intersection) / len(union)
        return similarity > 0.6
    
    def _merge_items(self, items: List[ActionItem]) -> ActionItem:
        base_item = items[0]
        
        for item in items[1:]:
            if item.confidence > base_item.confidence:
                base_item = item
                
        descriptions = [item.description for item in items]
        base_item.description = "\n\n".join(descriptions)
        
        return base_item


class MeetingMinutesGenerator:
    def __init__(self):
        self.action_extractor = ActionItemExtractor()
        self.ollama_available = self._check_ollama()
        
    def _check_ollama(self) -> bool:
        try:
            result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
            return result.returncode == 0
        except:
            logger.warning("Ollama not available, using rule-based generation")
            return False
            
    async def generate_minutes(
        self,
        transcription: TranscriptionResult,
        meeting_title: str,
        meeting_date: datetime,
        participants: List[str]
    ) -> MeetingMinutes:
        
        action_items = self.action_extractor.extract_action_items(transcription.segments)
        
        summary = await self._generate_summary(transcription)
        key_decisions = self._extract_key_decisions(transcription)
        next_steps = self._extract_next_steps(transcription, action_items)
        
        return MeetingMinutes(
            meeting_title=meeting_title,
            meeting_date=meeting_date,
            participants=participants,
            summary=summary,
            transcription_id=transcription.id,
            action_items=action_items,
            key_decisions=key_decisions,
            next_steps=next_steps
        )
    
    async def _generate_summary(self, transcription: TranscriptionResult) -> str:
        if self.ollama_available:
            return await self._generate_summary_with_llm(transcription)
        else:
            return self._generate_summary_rule_based(transcription)
            
    async def _generate_summary_with_llm(self, transcription: TranscriptionResult) -> str:
        prompt = f"""以下の会議記録を要約してください。重要なポイントを3-5個の箇条書きにしてください：

{transcription.corrected_text[:2000]}

要約："""
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                temp_path = f.name
                
            result = subprocess.run(
                ['ollama', 'run', 'llama3', f'< {temp_path}'],
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            Path(temp_path).unlink()
            
            if result.returncode == 0:
                return result.stdout.strip()
                
        except Exception as e:
            logger.error(f"LLM summary generation failed: {e}")
            
        return self._generate_summary_rule_based(transcription)
    
    def _generate_summary_rule_based(self, transcription: TranscriptionResult) -> str:
        text = transcription.corrected_text
        sentences = text.split('。')
        
        important_sentences = []
        importance_keywords = ['決定', '重要', '確認', '合意', '方針', '計画', '予定', '課題', '問題']
        
        for sentence in sentences:
            if any(keyword in sentence for keyword in importance_keywords):
                important_sentences.append(sentence.strip() + '。')
                
        if len(important_sentences) > 5:
            important_sentences = important_sentences[:5]
            
        if not important_sentences:
            words = text.split()
            if len(words) > 100:
                summary = ' '.join(words[:100]) + '...'
            else:
                summary = text
            return summary
            
        return '\n'.join([f"• {sent}" for sent in important_sentences])
    
    def _extract_key_decisions(self, transcription: TranscriptionResult) -> List[str]:
        decisions = []
        decision_patterns = [
            r'(?:決定|決まり|確定).*?(?:しました|します|した)',
            r'(?:方針|方向性).*?(?:とする|にする|で進める)',
            r'(?:承認|了承|合意).*?(?:されました|しました|を得ました)',
        ]
        
        text = transcription.corrected_text
        sentences = text.split('。')
        
        for sentence in sentences:
            for pattern in decision_patterns:
                if re.search(pattern, sentence):
                    decisions.append(sentence.strip() + '。')
                    break
                    
        return decisions[:5]
    
    def _extract_next_steps(self, transcription: TranscriptionResult, action_items: List[ActionItem]) -> List[str]:
        next_steps = []
        
        high_priority_items = [item for item in action_items if item.priority == ActionItemPriority.HIGH]
        for item in high_priority_items[:3]:
            step = f"{item.title}"
            if item.assignee:
                step += f" ({item.assignee})"
            if item.due_date:
                step += f" - {item.due_date.strftime('%Y/%m/%d')}まで"
            next_steps.append(step)
            
        next_meeting_patterns = [
            r'次回.*?(?:会議|打ち合わせ|ミーティング).*?(\d+月\d+日)',
            r'(\d+月\d+日).*?(?:会議|打ち合わせ|ミーティング)',
        ]
        
        for pattern in next_meeting_patterns:
            match = re.search(pattern, transcription.corrected_text)
            if match:
                next_steps.append(f"次回会議: {match.group(1)}")
                break
                
        return next_steps
    
    def save_minutes(self, minutes: MeetingMinutes, db: Session) -> int:
        db_minutes = MeetingMinutesDB(
            meeting_title=minutes.meeting_title,
            meeting_date=minutes.meeting_date,
            participants=json.dumps(minutes.participants, ensure_ascii=False),
            summary=minutes.summary,
            transcription_id=minutes.transcription_id,
            key_decisions=json.dumps(minutes.key_decisions, ensure_ascii=False),
            next_steps=json.dumps(minutes.next_steps, ensure_ascii=False)
        )
        
        db.add(db_minutes)
        db.commit()
        db.refresh(db_minutes)
        
        for action_item in minutes.action_items:
            db_action = ActionItemDB(
                title=action_item.title,
                description=action_item.description,
                assignee=action_item.assignee,
                due_date=action_item.due_date,
                priority=action_item.priority.value,
                status=action_item.status.value,
                source_segment=json.dumps(action_item.source_segment.dict() if action_item.source_segment else None, ensure_ascii=False),
                confidence=action_item.confidence,
                meeting_minutes_id=db_minutes.id
            )
            db.add(db_action)
            
        db.commit()
        
        return db_minutes.id