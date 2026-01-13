import unittest
from pathlib import Path
import tempfile
import shutil

def gather_full_context(completed_sections: list[str]) -> str:
    """
    Merges all completed Markdown sections into a single string for full-context review.
    """
    context_parts = []
    for section_path in completed_sections:
        path = Path(section_path)
        if path.exists():
            content = path.read_text(encoding="utf-8")
            context_parts.append(f"<!-- START SECTION: {path.name} -->\n{content}\n<!-- END SECTION: {path.name} -->")
    return "\n\n".join(context_parts)

class TestContextGathering(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.section1 = self.test_dir / "chapter1.md"
        self.section1.write_text("# Chapter 1\nContent 1", encoding="utf-8")
        self.section2 = self.test_dir / "chapter2.md"
        self.section2.write_text("# Chapter 2\nContent 2", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_gather_context(self):
        sections = [str(self.section1), str(self.section2)]
        context = gather_full_context(sections)
        
        self.assertIn("# Chapter 1", context)
        self.assertIn("# Chapter 2", context)
        self.assertIn("<!-- START SECTION: chapter1.md -->", context)
        self.assertIn("<!-- END SECTION: chapter2.md -->", context)

if __name__ == "__main__":
    unittest.main()

