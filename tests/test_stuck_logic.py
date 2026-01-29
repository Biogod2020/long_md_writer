import unittest
from src.core.patcher import StuckDetector
from src.core.types import AgentState

class TestStuckLogic(unittest.TestCase):
    def test_stuck_detector_basic(self):
        detector = StuckDetector()
        content = "Line 1\nLine 2"
        advice = "Fix Line 1"
        
        # First time - not stuck
        self.assertTrue(detector.check_progress(advice, content))
        
        # Second time with same content - STUCK
        self.assertFalse(detector.check_progress(advice, content))
        
        # Change content - NOT STUCK
        content = "Line 1 updated\nLine 2"
        self.assertTrue(detector.check_progress(advice, content))
        
        # Change advice - NOT STUCK
        advice = "Fix Line 2"
        self.assertTrue(detector.check_progress(advice, content))

    def test_loop_metadata_retry_logic(self):
        # Simulate EditorialQA retry logic using AgentState
        state = AgentState(
            user_context="test",
            workspace_path="workspace_test",
            job_id="test_job"
        )
        
        namespace = "s1"
        retry_key = f"qa_retry_{namespace}"
        
        # Initial state
        self.assertFalse(state.loop_metadata.get(retry_key, False))
        
        # First fail -> set retry
        state.loop_metadata[retry_key] = True
        self.assertTrue(state.loop_metadata.get(retry_key))
        
        # Second check -> true means we already retried
        if state.loop_metadata.get(retry_key):
            # This would break the loop in the agent
            pass
            
        # Reset on success
        state.loop_metadata[retry_key] = False
        self.assertFalse(state.loop_metadata.get(retry_key))

if __name__ == "__main__":
    unittest.main()
