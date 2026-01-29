from src.core.patcher import apply_smart_patch

def verify():
    print("--- Verifying Universal Patcher (Native Bridge + Fallback) ---")
    
    # Test 1: Flexible Indentation (Aider style)
    content = "class MyClass:\n    def method(self):\n        pass"
    search = "def method(self):\n    pass" # No base indentation in search
    replace = "def method(self):\n    return True"
    
    result, success = apply_smart_patch(content, search, replace)
    print(f"Test 1 (Flexible Indent): {'SUCCESS' if success else 'FAILED'}")
    if success:
        print("Result content:")
        print(result)
    
    # Test 2: Regex Tokenized (gemini-cli style)
    content = "const x = 10;  const y = 20;"
    search = "const x=10; const y=20;" # Different spacing
    replace = "const x = 100; const y = 200;"
    
    result, success = apply_smart_patch(content, search, replace)
    print(f"\nTest 2 (Regex Tokenized): {'SUCCESS' if success else 'FAILED'}")
    if success:
        print("Result content:")
        print(result)

    # Test 3: Fuzzy Fallback (DMP)
    content = "The quick brown fox jumps over the lazy dog."
    search = "The quick bron fox jumps" # Typo
    replace = "The fast brown fox jumps"
    
    result, success = apply_smart_patch(content, search, replace)
    print(f"\nTest 3 (Fuzzy Fallback): {'SUCCESS' if success else 'FAILED'}")
    if success:
        print("Result content:")
        print(result)

if __name__ == "__main__":
    verify()
