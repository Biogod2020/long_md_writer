import unittest
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.patcher import StuckDetector

class TestStuckDetector(unittest.TestCase):
    def test_detection_no_change(self):
        detector = StuckDetector()
        content = "initial content"
        
        # First iteration
        progress = detector.check_progress("fix advice", content)
        self.assertTrue(progress)
        
        # Second iteration, same content
        progress = detector.check_progress("fix advice", content)
        self.assertFalse(progress)

    def test_not_stuck_if_content_changes(self):
        detector = StuckDetector()
        content1 = "initial content"
        content2 = "modified content"
        
        progress = detector.check_progress("fix advice", content1)
        self.assertTrue(progress)
        
        progress = detector.check_progress("fix advice", content2)
        self.assertTrue(progress)

    def test_different_advice_not_stuck(self):
        detector = StuckDetector()
        content = "initial content"
        
        progress = detector.check_progress("fix advice 1", content)
        self.assertTrue(progress)
        
        # Different advice should reset or count as new attempt
        progress = detector.check_progress("fix advice 2", content)
        self.assertTrue(progress)

if __name__ == "__main__":
    unittest.main()
