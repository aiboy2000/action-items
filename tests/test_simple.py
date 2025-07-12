import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.models import TermType, ActionItemPriority, ActionItemStatus


class TestEnums(unittest.TestCase):
    
    def test_term_type_enum(self):
        self.assertEqual(TermType.TECHNICAL.value, "technical")
        self.assertEqual(TermType.MATERIAL.value, "material")
        self.assertEqual(TermType.SAFETY.value, "safety")
        
    def test_action_item_priority(self):
        self.assertEqual(ActionItemPriority.HIGH.value, "high")
        self.assertEqual(ActionItemPriority.MEDIUM.value, "medium")
        self.assertEqual(ActionItemPriority.LOW.value, "low")
        
    def test_action_item_status(self):
        self.assertEqual(ActionItemStatus.PENDING.value, "pending")
        self.assertEqual(ActionItemStatus.IN_PROGRESS.value, "in_progress")
        self.assertEqual(ActionItemStatus.COMPLETED.value, "completed")
        self.assertEqual(ActionItemStatus.CANCELLED.value, "cancelled")


if __name__ == '__main__':
    unittest.main()