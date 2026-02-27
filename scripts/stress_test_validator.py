import sys
from pathlib import Path

# 确保能导入 src
sys.path.append(str(Path(__file__).parent.parent))

from src.core.validators import MarkdownValidator, ValidationSeverity

def run_test():
    validator = MarkdownValidator()
    
    test_cases = [
        {
            "name": "Standard valid blocks",
            "content": "\n# Title\n:::important\nKey point\n:::\n\n:::visual {\"id\": \"v1\", \"action\": \"GENERATE_SVG\", \"description\": \"test\"}\nDrawing...\n:::\n",
            "should_be_valid": True
        },
        {
            "name": "Title-style blocks (Currently failing due to regex)",
            "content": "\n:::tip [Physical View]\nThis is a standard custom container title.\n:::\n",
            "should_be_valid": True
        },
        {
            "name": "Inline triple colons (Should be ignored)",
            "content": "This text contains ::: inline, it should not trigger the validator.",
            "should_be_valid": True
        },
        {
            "name": "Indented closing tag (Edge case)",
            "content": "\n:::note\n    :::\n",
            "should_be_valid": False
        },
        {
            "name": "Complex nested blocks",
            "content": "\n:::important\nMain level\n:::tip Sub title\nNested level\n:::\nBack to main\n:::\n",
            "should_be_valid": True
        },
        {
            "name": "Math formula with colons",
            "content": "\n$$\nf(x) = y ::: z\n$$\n",
            "should_be_valid": True
        }
    ]

    print("🚀 Starting Stress Test for MarkdownValidator...\n")
    
    failed_any = False
    for case in test_cases:
        result = validator.validate_all(case["content"])
        is_actually_valid = result.is_valid
        
        status = "✅ PASS" if is_actually_valid == case["should_be_valid"] else "❌ FAIL"
        
        print(f"Test: {case['name']}")
        print(f"  Result: {status}")
        
        if is_actually_valid != case["should_be_valid"]:
            failed_any = True
            print(f"  Expected Valid: {case['should_be_valid']}, Got: {is_actually_valid}")
            for issue in result.issues:
                if issue.severity == ValidationSeverity.ERROR:
                    print(f"  Error: {issue.message} at line {issue.line_number}")
        print("-" * 40)

    if failed_any:
        print("\n❌ Stress test identified logic gaps or false positives.")
    else:
        print("\n✨ All test cases behaved exactly as expected.")

if __name__ == "__main__":
    run_test()
