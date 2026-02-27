import re
from pathlib import Path

def apply_manual_fixes(md_path: str):
    p = Path(md_path)
    if not p.exists(): return
    content = p.read_text(encoding="utf-8")
    
    print(f"🛠️ Applying physical fixes to {md_path}...")
    
    # 1. Promote H3 to H2 (Global)
    content = content.replace("\n### ", "\n## ")
    
    # 2. Fix Section 5 title duplication
    s5_search = '<!-- SECTION: s5-sec-05 -->\n# Horizontal Depth: The Precordial Siege\n\n# 横向深度：胸前导联的“围攻” (Horizontal Depth: The Precordial Siege)'
    s5_replace = '<!-- SECTION: s5-sec-05 -->\n# 横向深度：胸前导联的“围攻” (Horizontal Depth: The Precordial Siege)'
    content = content.replace(s5_search, s5_replace)
    
    # 3. Fix Section 6 title duplication
    s6_search = '<!-- SECTION: s6-sec-06 -->\n# Synthesis: The 12-View Cardiac Movie\n\n# 综合：12 视角的心脏电影 (Synthesis: The 12-View Cardiac Movie)'
    s6_replace = '<!-- SECTION: s6-sec-06 -->\n# 综合：12 视角的心脏电影 (Synthesis: The 12-View Cardiac Movie)'
    content = content.replace(s6_search, s6_replace)
    
    # 4. Remove residual visual directive in S2 (Found in ADVICER feedback)
    # Pattern matching the specific block mentioned in Step 2 of Advice
    content = re.sub(r'具有极高的临床精度。\n\n:::visual.*?### 2.2 双极肢体导联的数学定义', 
                     '具有极高的临床精度。\n\n## 2.2 双极肢体导联的数学定义', 
                     content, flags=re.DOTALL)

    p.write_text(content, encoding="utf-8")
    print("✅ Physical fixes applied.")

if __name__ == "__main__":
    apply_manual_fixes("workspace/sota2_20260223_220554/final_full.md")
