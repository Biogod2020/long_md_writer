
import json
from src.core.json_utils import parse_json_dict_robust

def stress_test_json_patcher():
    test_cases = [
        # 1. Standard LaTeX issue (The one we just found)
        r'{"id": "test1", "desc": "$\vec{P}$ and $\theta$"}',
        
        # 2. Unescaped backslashes in paths
        r'{"path": "C:\Users\Jay\Documents"}',
        
        # 3. Mixing valid and invalid escapes
        r'{"text": "Line 1\nLine 2 with \invalid escape"}',
        
        # 4. Trailing commas (LLM classic)
        r'{"id": "test4", "list": [1, 2, 3,],}',
        
        # 5. Unescaped newlines in values
        '{"id": "test5", "desc": "This is a \n multi-line string"}',
        
        # 6. Truncated JSON
        r'{"id": "test6", "feedback": "The image is look'
    ]
    
    print("🚀 Starting JSON Patcher Stress Test...")
    for i, case in enumerate(test_cases):
        print(f"\n--- Case {i+1} ---")
        print(f"Input: {case}")
        result = parse_json_dict_robust(case)
        if result:
            print(f"✅ Success: {result}")
        else:
            print(f"❌ FAILED")

if __name__ == "__main__":
    stress_test_json_patcher()
