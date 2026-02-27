import os
import shutil
import unittest
from pathlib import Path
from src.core.merger import merge_markdown_sections
from src.core.types import UniversalAssetRegistry, AssetEntry, AssetSource, CropMetadata

class TestMergerRobustness(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("temp_merger_test").absolute()
        self.test_dir.mkdir(exist_ok=True)
        self.workspace = self.test_dir / "workspace"
        self.workspace.mkdir(exist_ok=True)
        self.md_dir = self.workspace / "md"
        self.md_dir.mkdir(exist_ok=True)
        self.gen_dir = self.workspace / "agent_generated"
        self.gen_dir.mkdir(exist_ok=True)
        
        # Create a mock asset
        self.asset_file = self.gen_dir / "test-fig.svg"
        self.asset_file.write_text("<svg>Test</svg>")
        
        self.uar = UniversalAssetRegistry()
        self.uar.set_persist_path(str(self.workspace / "assets.json"))
        self.entry = AssetEntry(
            id="s1-fig-test",
            source=AssetSource.AI,
            local_path=str(self.asset_file.relative_to(self.workspace)),
            semantic_label="Test Asset"
        )
        self.uar.register_immediate(self.entry)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_absolute_path_handling(self):
        """测试：输入绝对路径时，不应产生双重拼接"""
        md_file = self.md_dir / "sec-01.md"
        # 构造包含多种引号和空格的 <img> 标签
        md_file.write_text('![img](...) <img src="../agent_generated/test-fig.svg" data-asset-id="s1-fig-test">')
        
        output_path = self.workspace / "final_full.md"
        
        # 模拟 E2E 场景：传入绝对路径列表
        success = merge_markdown_sections(
            [str(md_file.absolute())],
            str(output_path.absolute()),
            workspace_path=str(self.workspace.absolute()),
            asset_registry=self.uar
        )
        
        self.assertTrue(success)
        self.assertTrue(output_path.exists())
        
        content = output_path.read_text()
        # 验证路径重定向
        self.assertIn('src="resource/test-fig.svg"', content)
        # 验证物理拷贝
        self.assertTrue((self.workspace / "resource" / "test-fig.svg").exists())
        print("  ✅ Absolute path handling passed.")

    def test_regex_robustness(self):
        """测试：各种奇葩的 HTML 标签格式"""
        md_file = self.md_dir / "sec-02.md"
        md_content = """
        1. 标准: <img src="old" data-asset-id="s1-fig-test">
        2. 大写: <IMG SRC='old' data-asset-id="s1-fig-test">
        3. 等号空格: <img src  =  "old" data-asset-id="s1-fig-test">
        4. 单引号: <img src='old' data-asset-id="s1-fig-test">
        """
        md_file.write_text(md_content)
        
        output_path = self.workspace / "final_full_regex.md"
        merge_markdown_sections(
            [str(md_file)],
            str(output_path),
            workspace_path=str(self.workspace),
            asset_registry=self.uar
        )
        
        content = output_path.read_text()
        # 检查是否所有的 src 都被重写为 resource/test-fig.svg
        matches = content.count('src="resource/test-fig.svg"') + content.count("src='resource/test-fig.svg'")
        # 注意：由于代码中统一改成了 src="resource/..."，所以应该都是双引号
        self.assertEqual(content.count('src="resource/test-fig.svg"'), 4)
        print("  ✅ Regex robustness passed.")

    def test_stress_large_assets(self):
        """压力测试：100 个章节 + 100 个资产"""
        section_paths = []
        for i in range(100):
            aid = f"s1-fig-{i}"
            img_name = f"img_{i}.png"
            img_file = self.gen_dir / img_name
            img_file.write_text(f"content {i}")
            
            entry = AssetEntry(
                id=aid,
                source=AssetSource.AI,
                local_path=str(img_file.relative_to(self.workspace)),
                semantic_label=f"Asset {i}"
            )
            self.uar.register_immediate(entry)
            
            md_file = self.md_dir / f"sec-{i}.md"
            md_file.write_text(f"Section {i}\n<img src='old' data-asset-id='{aid}'>")
            section_paths.append(str(md_file))
            
        output_path = self.workspace / "stress_full.md"
        success = merge_markdown_sections(
            section_paths,
            str(output_path),
            workspace_path=str(self.workspace),
            asset_registry=self.uar
        )
        
        self.assertTrue(success)
        # 检查物理拷贝数量
        resource_files = list((self.workspace / "resource").glob("*.png"))
        self.assertEqual(len(resource_files), 100)
        print("  ✅ Stress test (100 sections/assets) passed.")

if __name__ == "__main__":
    unittest.main()
