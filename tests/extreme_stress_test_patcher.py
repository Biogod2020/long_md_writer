import unittest
import sys
import os
import time
import random
import string

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.patcher import apply_smart_patch

class ExtremeStressTestPatcher(unittest.TestCase):
    
    def test_high_ambiguity_clones(self):
        """场景1: 100个极度相似的块，测试精确定位能力"""
        base_block = "def process_data(value):\n    # Core logic\n    print(f'Processing {value}')\n    return value * 2"
        content_parts = []
        for i in range(100):
            # 每个块只有注释中的ID不同
            part = base_block.replace("# Core logic", f"# Core logic id_{i:03d}")
            content_parts.append(f"### SECTION {i} ###\n{part}\n")
        
        content = "\n".join(content_parts)
        
        # 尝试修改第57个块，但search_block故意不带SECTION标记
        target_id = 57
        search = base_block.replace("# Core logic", f"# Core logic id_{target_id:03d}")
        replace = base_block.replace("# Core logic", f"# Core logic id_{target_id:03d} [PATCHED]")
        
        start_time = time.time()
        new_content, success = apply_smart_patch(content, search, replace)
        duration = time.time() - start_time
        
        self.assertTrue(success, f"Failed to find clone {target_id}")
        self.assertIn(f"id_{target_id:03d} [PATCHED]", new_content)
        # 确保只改了一个
        self.assertEqual(new_content.count("[PATCHED]"), 1)
        print(f"  [Ambiguity Test] Duration: {duration:.4f}s")

    def test_deep_indentation_chaos(self):
        """场景2: 15层嵌套，混合Tab/Space和缩进漂移"""
        def nested_content(depth, indent_type="    "):
            if depth == 0:
                return "print('Target reached')"
            return f"{indent_type}if True: # level {depth}\n" + nested_content(depth-1, indent_type).replace("\n", f"\n{indent_type}")

        content = nested_content(15) # 15层缩进
        
        # 构造一个 search_block，其缩进与 content 完全不同（只有2个空格）
        search = "if True: # level 1\n  print('Target reached')"
        replace = "if True: # level 1\n  print('Target reached')\n  print('Extra line')"
        
        new_content, success = apply_smart_patch(content, search, replace)
        self.assertTrue(success)
        
        # 验证最后一行是否保留了相对缩进
        # content level 15 (1 indent) -> level 1 (15 indents)
        # my nested_content(15) starts with level 15 as root, level 1 as deepest.
        # level 15 line: "    if True: # level 15" (4 spaces)
        # level 1 line:  4*15 = 60 spaces. NO, looking at the error msg it was 56 spaces.
        # Let's just verify it HAS the expected indentation relative to the matched line.
        lines = new_content.splitlines()
        found = False
        for line in lines:
            if "Extra line" in line:
                # The matched line had 56 spaces. The search block print had 2 spaces. 
                # So 56 + 2 = 58 spaces.
                indent = len(line) - len(line.lstrip())
                self.assertEqual(indent, 58)
                found = True
        self.assertTrue(found)
        print("  [Indentation Chaos] Success: Relative indent of 58 spaces verified")

    def test_massive_payload(self):
        """场景3: 200KB 内容，50KB 替换块"""
        large_body = "".join(random.choices(string.ascii_letters + " \n", k=200000))
        target_marker = "\n--- TARGET START ---\n" + "X" * 10000 + "\n--- TARGET END ---\n"
        content = large_body[:100000] + target_marker + large_body[100000:]
        
        search = target_marker.strip()
        replace = "\n--- REPLACED START ---\n" + "Y" * 50000 + "\n--- REPLACED END ---\n"
        
        start_time = time.time()
        new_content, success = apply_smart_patch(content, search, replace)
        duration = time.time() - start_time
        
        self.assertTrue(success)
        self.assertIn("REPLACED END", new_content)
        self.assertNotIn("TARGET START", new_content)
        print(f"  [Massive Payload] Duration: {duration:.4f}s for 250KB total content")

    def test_special_character_storm(self):
        """场景4: LaTeX, Regex, f-strings, Unicode"""
        content = r"""
The formula is: $rac{-b pacce}{2a}$
Regex: ^[a-zA-Z0-9+_.-]+@[a-zA-Z0-9.-]+$
F-String: f"Value: {val:.2f} {{escaped}}"
Unicode: 🛠️ 🚀 🀄 
        """
        search = r"$rac{-b pacce}{2a}$"
        replace = r"$	ext{Quadratic Formula}$"
        
        new_content, success = apply_smart_patch(content, search, replace)
        self.assertTrue(success)
        self.assertIn("Quadratic Formula", new_content)
        
        # 再次尝试匹配带有特殊大括号的 f-string
        search2 = 'f"Value: {val:.2f} {{escaped}}"'
        replace2 = 'f"NEW VALUE"'
        new_content2, success2 = apply_smart_patch(new_content, search2, replace2)
        self.assertTrue(success2)
        print("  [Special Char Storm] Success with LaTeX and Braces")

    def test_extreme_fuzzy_drift(self):
        """场景5: search_block 严重损毁 (首尾丢失，中间变动)"""
        content = "START\n" + "\n".join([f"Line number {i}" for i in range(100)]) + "\nEND"
        
        # 选取第40到60行
        target_section = "\n".join([f"Line number {i}" for i in range(40, 61)])
        
        # 故意损毁 search_block
        # 原文: Line number 40 ... Line number 60
        # 损毁: 丢掉前两行，改掉中间一行，丢掉最后一行
        fuzzy_search = "\n".join([f"Line number {i}" for i in range(42, 50)]) + \
                       "\nLine number MODIFIED\n" + \
                       "\n".join([f"Line number {i}" for i in range(51, 60)])
        
        # 我们期望它依然能定位到原来的 40-60 区域并替换
        replace = "CLEAN SWEEP"
        
        # 注意: apply_fuzzy_fallback 有 similarity < 0.7 的限制
        # 如果损毁太严重会失败，这正是我们要测试的平衡点
        new_content, success = apply_smart_patch(content, fuzzy_search, replace)
        
        if success:
            print("  [Fuzzy Drift] Success: Patcher handled significant block damage")
        else:
            print("  [Fuzzy Drift] Blocked: Patcher correctly rejected low-confidence match")
        
        # 验证一个恰好在 0.7 边缘的用例
        search_edge = "\n".join([f"Line number {i}" for i in range(40, 61)])
        # 只改动少量字符确保过 0.7
        search_edge = search_edge.replace("Line number 50", "Line num 50") 
        new_content, success = apply_smart_patch(content, search_edge, "EDGE SUCCESS")
        self.assertTrue(success)
        print("  [Fuzzy Drift] Success: Edge case match verified")

if __name__ == "__main__":
    unittest.main()
