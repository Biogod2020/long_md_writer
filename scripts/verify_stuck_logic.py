from src.core.patcher import StuckDetector

def verify_stuck_logic():
    print("--- Verifying Stuck Detection Logic ---")
    detector = StuckDetector()
    
    content = "Hello world"
    advice = "Change Hello to Hi"
    
    # First time
    res1 = detector.check_progress(advice, content)
    print(f"Iteration 1 Progress: {res1} (Expected: True)")
    
    # Second time, same content (failed to patch)
    res2 = detector.check_progress(advice, content)
    print(f"Iteration 2 Progress: {res2} (Expected: False - STUCK)")
    
    # Third time, content changed
    new_content = "Hi world"
    res3 = detector.check_progress(advice, new_content)
    print(f"Iteration 3 Progress: {res3} (Expected: True)")

if __name__ == "__main__":
    verify_stuck_logic()
