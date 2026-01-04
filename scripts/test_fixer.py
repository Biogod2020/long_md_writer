"""
Test Fixer Agent in Isolation
Verifies that Fixer can correctly generate and apply code fixes.
"""

import os
from pathlib import Path
from src.core.gemini_client import GeminiClient
from src.agents.visual_qa.fixer import run_fixer, apply_fix

def test_fixer():
    # Setup
    api_base_url = "http://localhost:7860"
    auth_token = os.getenv("GEMINI_AUTH_PASSWORD", "123456")
    client = GeminiClient(api_base_url=api_base_url, auth_token=auth_token)
    
    workspace_path = "workspace_debug/debug_201956"
    section_path = f"{workspace_path}/html/sec-1.html"
    
    # Create a test issue (simulating what Critic would return)
    test_issue = {
        "id": "test-issue-1",
        "severity": "major",
        "location": "PART 2, scroll 800px, inside the SVG diagram",
        "element": "The formula 'V_ecg = |P| cos θ'",
        "problem": "The subscript 'ecg' is rendered as a literal underscore instead of proper SVG subscript formatting."
    }
    
    print("=" * 50)
    print("Testing Fixer Agent")
    print("=" * 50)
    print(f"\nIssue: {test_issue['problem']}")
    print(f"Section: {section_path}")
    
    # Read original content for comparison
    original_content = Path(section_path).read_text(encoding="utf-8")
    
    # Run Fixer
    print("\n🔧 Running Fixer...")
    fix_result = run_fixer(
        client=client,
        issue=test_issue,
        section_path=section_path,
        workspace_path=workspace_path,
        debug=True
    )
    
    if not fix_result:
        print("\n❌ Fixer returned None")
        return
    
    print(f"\n📋 Fixer Result:")
    print(f"   Status: {fix_result.get('status')}")
    print(f"   Target File: {fix_result.get('target_file')}")
    print(f"   Explanation: {fix_result.get('explanation', 'N/A')}")
    
    if fix_result.get("status") == "FIXED":
        fix = fix_result.get("fix", {})
        print(f"\n   Fix Type: {fix.get('type')}")
        print(f"   Target: {fix.get('target')[:100]}..." if fix.get('target') else "   Target: N/A")
        print(f"   Replacement: {fix.get('replacement')[:100]}..." if fix.get('replacement') else "   Replacement: N/A")
        
        # Ask before applying
        confirm = input("\n⚠️ Apply this fix? (y/n): ")
        if confirm.lower() == 'y':
            applied = apply_fix(fix_result, workspace_path)
            if applied:
                print("✅ Fix applied successfully!")
                
                # Show diff
                new_content = Path(section_path).read_text(encoding="utf-8")
                if original_content != new_content:
                    print("\n📊 File was modified.")
            else:
                print("❌ Failed to apply fix.")
        else:
            print("Skipped applying fix.")
    else:
        print(f"   Reason: {fix_result.get('reason', 'Unknown')}")

if __name__ == "__main__":
    test_fixer()
