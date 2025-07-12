import re
from typing import List, Dict, Set, Tuple
from collections import Counter
import logging
from ..core.models import ActionItem, Tag
from ..core.database import TagDB, ActionItemDB, get_db
from sqlalchemy.orm import Session
from sqlalchemy import and_

logger = logging.getLogger(__name__)


class SmartTagger:
    def __init__(self):
        self.tag_rules = {
            "安全": {
                "keywords": ["安全", "危険", "事故", "防護", "保護具", "KY", "リスク", "災害"],
                "category": "safety",
                "color": "#FF0000"
            },
            "品質": {
                "keywords": ["品質", "検査", "試験", "基準", "規格", "不良", "是正"],
                "category": "quality",
                "color": "#0000FF"
            },
            "工程": {
                "keywords": ["工程", "スケジュール", "遅延", "進捗", "工期", "納期"],
                "category": "schedule",
                "color": "#00FF00"
            },
            "コスト": {
                "keywords": ["コスト", "費用", "予算", "見積", "原価", "経費"],
                "category": "cost",
                "color": "#FFD700"
            },
            "設計変更": {
                "keywords": ["設計変更", "変更", "修正", "改訂", "見直し"],
                "category": "change",
                "color": "#FF00FF"
            },
            "資材": {
                "keywords": ["資材", "材料", "調達", "発注", "納入", "在庫"],
                "category": "material",
                "color": "#00FFFF"
            },
            "協力会社": {
                "keywords": ["協力会社", "下請", "業者", "外注", "委託"],
                "category": "subcontractor",
                "color": "#FFA500"
            },
            "環境": {
                "keywords": ["環境", "騒音", "振動", "粉塵", "廃棄物", "リサイクル"],
                "category": "environment",
                "color": "#008000"
            },
            "許可申請": {
                "keywords": ["許可", "申請", "届出", "承認", "認可", "手続き"],
                "category": "permit",
                "color": "#800080"
            },
            "緊急": {
                "keywords": ["緊急", "至急", "即日", "本日中", "早急"],
                "category": "urgency",
                "color": "#DC143C"
            }
        }
        
        self.phase_tags = {
            "基礎工事": ["基礎", "杭", "地盤", "掘削", "土工事"],
            "躯体工事": ["躯体", "鉄筋", "型枠", "コンクリート", "鉄骨"],
            "仕上工事": ["仕上", "内装", "外装", "塗装", "防水"],
            "設備工事": ["設備", "電気", "空調", "衛生", "配管"],
        }
        
    def extract_tags(self, action_item: ActionItem) -> List[str]:
        text = f"{action_item.title} {action_item.description}".lower()
        tags = []
        
        for tag_name, rule in self.tag_rules.items():
            if any(keyword in text for keyword in rule["keywords"]):
                tags.append(tag_name)
                
        phase_tags = self._extract_phase_tags(text)
        tags.extend(phase_tags)
        
        priority_tag = self._get_priority_tag(action_item)
        if priority_tag:
            tags.append(priority_tag)
            
        if action_item.due_date:
            tags.append("期限あり")
            
        if action_item.assignee:
            tags.append(f"担当:{action_item.assignee}")
            
        tags = list(set(tags))
        
        return tags[:10]
    
    def _extract_phase_tags(self, text: str) -> List[str]:
        phase_tags = []
        
        for phase_name, keywords in self.phase_tags.items():
            if any(keyword in text for keyword in keywords):
                phase_tags.append(phase_name)
                
        return phase_tags
    
    def _get_priority_tag(self, action_item: ActionItem) -> str:
        priority_map = {
            "high": "重要度:高",
            "medium": "重要度:中",
            "low": "重要度:低"
        }
        return priority_map.get(action_item.priority.value, "")
    
    def create_or_get_tags(self, tag_names: List[str], db: Session) -> List[TagDB]:
        tags = []
        
        for tag_name in tag_names:
            existing_tag = db.query(TagDB).filter(TagDB.name == tag_name).first()
            
            if existing_tag:
                tags.append(existing_tag)
            else:
                tag_info = self._get_tag_info(tag_name)
                new_tag = TagDB(
                    name=tag_name,
                    category=tag_info["category"],
                    color=tag_info["color"],
                    description=tag_info["description"]
                )
                db.add(new_tag)
                db.commit()
                db.refresh(new_tag)
                tags.append(new_tag)
                
        return tags
    
    def _get_tag_info(self, tag_name: str) -> Dict[str, str]:
        for rule_name, rule in self.tag_rules.items():
            if tag_name == rule_name:
                return {
                    "category": rule["category"],
                    "color": rule["color"],
                    "description": f"{rule_name}に関連するアクションアイテム"
                }
                
        if tag_name.startswith("担当:"):
            return {
                "category": "assignee",
                "color": "#696969",
                "description": f"{tag_name[3:]}が担当するアクションアイテム"
            }
            
        if tag_name.startswith("重要度:"):
            return {
                "category": "priority",
                "color": "#FF6347",
                "description": f"{tag_name}のアクションアイテム"
            }
            
        if tag_name in self.phase_tags:
            return {
                "category": "phase",
                "color": "#4682B4",
                "description": f"{tag_name}フェーズのアクションアイテム"
            }
            
        return {
            "category": "other",
            "color": "#808080",
            "description": tag_name
        }
    
    def tag_action_item(self, action_item_id: int, db: Session):
        action_item = db.query(ActionItemDB).filter(ActionItemDB.id == action_item_id).first()
        
        if not action_item:
            logger.error(f"Action item {action_item_id} not found")
            return
            
        action_model = ActionItem(
            id=action_item.id,
            title=action_item.title,
            description=action_item.description,
            assignee=action_item.assignee,
            due_date=action_item.due_date,
            priority=action_item.priority,
            status=action_item.status
        )
        
        tag_names = self.extract_tags(action_model)
        
        tags = self.create_or_get_tags(tag_names, db)
        
        action_item.tags = tags
        db.commit()
        
        logger.info(f"Tagged action item {action_item_id} with {len(tags)} tags")
    
    def tag_all_action_items(self, db: Session) -> Dict[str, int]:
        action_items = db.query(ActionItemDB).all()
        
        tagged_count = 0
        tag_count = 0
        
        for action_item in action_items:
            try:
                self.tag_action_item(action_item.id, db)
                tagged_count += 1
                tag_count += len(action_item.tags)
            except Exception as e:
                logger.error(f"Error tagging action item {action_item.id}: {e}")
                
        return {
            "tagged_items": tagged_count,
            "total_tags": tag_count
        }
    
    def find_related_items(self, action_item_id: int, db: Session, limit: int = 5) -> List[ActionItemDB]:
        action_item = db.query(ActionItemDB).filter(ActionItemDB.id == action_item_id).first()
        
        if not action_item or not action_item.tags:
            return []
            
        tag_ids = [tag.id for tag in action_item.tags]
        
        related_items = db.query(ActionItemDB).join(ActionItemDB.tags).filter(
            and_(
                ActionItemDB.id != action_item_id,
                TagDB.id.in_(tag_ids)
            )
        ).distinct().limit(limit).all()
        
        return related_items
    
    def get_tag_statistics(self, db: Session) -> Dict[str, Any]:
        tags = db.query(TagDB).all()
        
        stats = {
            "total_tags": len(tags),
            "tags_by_category": {},
            "most_used_tags": []
        }
        
        category_counter = Counter()
        tag_usage = []
        
        for tag in tags:
            category_counter[tag.category] += 1
            usage_count = len(tag.action_items)
            tag_usage.append((tag.name, usage_count))
            
        stats["tags_by_category"] = dict(category_counter)
        stats["most_used_tags"] = sorted(tag_usage, key=lambda x: x[1], reverse=True)[:10]
        
        return stats
    
    def search_by_tags(self, tag_names: List[str], db: Session) -> List[ActionItemDB]:
        query = db.query(ActionItemDB).join(ActionItemDB.tags)
        
        for tag_name in tag_names:
            query = query.filter(TagDB.name == tag_name)
            
        return query.distinct().all()
    
    def suggest_tags(self, partial_text: str, db: Session, limit: int = 10) -> List[str]:
        tags = db.query(TagDB).filter(
            TagDB.name.like(f"%{partial_text}%")
        ).limit(limit).all()
        
        return [tag.name for tag in tags]