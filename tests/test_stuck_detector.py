import unittest
from src.core.patcher import StuckDetector

class TestStuckDetector(unittest.TestCase):
    def test_detection_no_change(self):
        detector = StuckDetector()
        content = "initial content"
        
        # First iteration
        is_stuck = detector.is_stuck(content, "fix advice")
        self.assertFalse(is_stuck)
        
        # Second iteration, same content
        is_stuck = detector.is_stuck(content, "fix advice")
        self.assertTrue(is_stuck)

    def test_not_stuck_if_content_changes(self):
        detector = StuckDetector()
        content1 = "initial content"
        content2 = "modified content"
        
        is_stuck = detector.is_stuck(content1, "fix advice")
        self.assertFalse(is_stuck)
        
        is_stuck = detector.is_stuck(content2, "fix advice")
        self.assertFalse(is_stuck)

    def test_different_advice_not_stuck(self):
        detector = StuckDetector()
        content = "initial content"
        
        is_stuck = detector.is_stuck(content, "fix advice 1")
        self.assertFalse(is_stuck)
        
        # Different advice should reset or count as new attempt
        is_stuck = detector.is_stuck(content, "fix advice 2")
        self.assertFalse(is_stuck)

if __name__ == "__main__":
    unittest.main()
