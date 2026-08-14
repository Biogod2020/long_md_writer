from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE_PATH = Path(__file__).parents[1] / "python" / "validate_publication.py"
SPEC = importlib.util.spec_from_file_location("longwriter_validator", MODULE_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class ValidatorTest(unittest.TestCase):
    def make_workspace(self, *, article_text: str) -> Path:
        root = Path(tempfile.mkdtemp(prefix="longwriter-validator-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        (root / "assets").mkdir()
        project = {
            "schema_version": 1,
            "title": "Validator fixture",
            "objective": "Validate a deterministic publication",
            "audience": "engineers",
            "language": "en",
            "mode": "markdown",
            "sections": [
                {
                    "id": "intro",
                    "title": "Introduction",
                    "objective": "Explain the design",
                    "target_words": 8,
                    "required_evidence": [],
                }
            ],
            "quality_contract": {
                "minimum_section_ratio": 0.75,
                "minimum_total_ratio": 0.75,
                "minimum_review_score": 85,
                "require_zero_placeholders": True,
                "require_review": True,
            },
        }
        (root / "project.json").write_text(json.dumps(project, indent=2), encoding="utf-8")
        (root / "article.md").write_text(article_text, encoding="utf-8")
        (root / "assets" / "manifest.json").write_text(
            json.dumps({"schema_version": 2, "assets": []}, indent=2),
            encoding="utf-8",
        )
        return root

    @staticmethod
    def valid_article() -> str:
        return """# Validator fixture

<!-- longwriter:section intro:start -->
## Introduction

<!-- longwriter:chunk intro-01 section=intro:start -->
This deterministic article contains enough substantive words to satisfy the planned section target.
<!-- longwriter:chunk intro-01:end -->

<!-- longwriter:section intro:end -->
"""

    def test_valid_workspace_passes(self) -> None:
        root = self.make_workspace(article_text=self.valid_article())
        result = VALIDATOR.validate(root)
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["metrics"]["chunk_count"], 1)
        expected = hashlib.sha256((root / "article.md").read_bytes()).hexdigest()
        self.assertEqual(result["metrics"]["article_sha256"], expected)

    def test_placeholder_fails(self) -> None:
        root = self.make_workspace(article_text=self.valid_article().replace("substantive words", "TODO substantive words"))
        result = VALIDATOR.validate(root)
        self.assertFalse(result["passed"])
        self.assertIn("article.placeholders", {failure["code"] for failure in result["failures"]})

    def test_malformed_chunk_fails(self) -> None:
        root = self.make_workspace(article_text=self.valid_article().replace("<!-- longwriter:chunk intro-01:end -->", ""))
        result = VALIDATOR.validate(root)
        self.assertFalse(result["passed"])
        self.assertIn("article.chunk_markers", {failure["code"] for failure in result["failures"]})


if __name__ == "__main__":
    unittest.main()
