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

    def make_visual_workspace(self) -> Path:
        article = self.valid_article().replace(
            "<!-- longwriter:chunk intro-01:end -->",
            "![Flow diagram](assets/svg/flow.svg)\n\n<!-- longwriter:chunk intro-01:end -->",
        )
        root = self.make_workspace(article_text=article)
        project_path = root / "project.json"
        project = json.loads(project_path.read_text(encoding="utf-8"))
        project["visual_contract"] = {
            "schema_version": 1,
            "figures": [{
                "id": "flow-figure",
                "section_id": "intro",
                "kind": "diagram",
                "purpose": "Show the flow.",
                "required_labels": ["Flow"],
                "review_required": True,
            }],
        }
        project_path.write_text(json.dumps(project, indent=2), encoding="utf-8")
        svg_path = root / "assets" / "svg" / "flow.svg"
        svg_path.parent.mkdir()
        svg_path.write_text(
            "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 100 60\"><text x=\"10\" y=\"30\">Flow</text></svg>",
            encoding="utf-8",
        )
        preview_path = root / "assets" / "reviews" / "flow-preview.png"
        preview_path.parent.mkdir()
        preview_path.write_bytes(b"\x89PNG\r\n\x1a\npreview")
        svg_sha = hashlib.sha256(svg_path.read_bytes()).hexdigest()
        preview_sha = hashlib.sha256(preview_path.read_bytes()).hexdigest()
        manifest = {
            "schema_version": 2,
            "assets": [
                {
                    "id": "flow-svg",
                    "source": "agent",
                    "path": "assets/svg/flow.svg",
                    "caption": "Flow diagram",
                    "alt_text": "A Flow diagram.",
                    "provenance": "agent_generated:svg-illustrator",
                    "licence": "generated_internal",
                    "used_in": ["intro"],
                    "sha256": svg_sha,
                    "visual_plan_id": "flow-figure",
                },
                {
                    "id": "flow-preview",
                    "source": "tool",
                    "path": "assets/reviews/flow-preview.png",
                    "caption": "Preview evidence",
                    "alt_text": "A raster preview.",
                    "provenance": "derived:svg-preflight",
                    "licence": "generated_internal",
                    "used_in": [],
                    "sha256": preview_sha,
                    "derivative_of": {
                        "asset_id": "flow-svg",
                        "asset_sha256": svg_sha,
                        "purpose": "svg-preview",
                    },
                },
            ],
            "visual_preflights": [{
                "id": "preflight-flow",
                "asset_id": "flow-svg",
                "asset_sha256": svg_sha,
                "visual_plan_id": "flow-figure",
                "preview_asset_id": "flow-preview",
                "preview_sha256": preview_sha,
                "metric_mode": "coretext",
                "renderer": "test-renderer",
                "passed": True,
                "issues": [],
                "warnings": [],
                "created_at": "2026-08-20T00:00:00.000Z",
            }],
            "visual_reviews": [{
                "id": "review-flow",
                "asset_id": "flow-svg",
                "asset_sha256": svg_sha,
                "visual_plan_id": "flow-figure",
                "preflight_id": "preflight-flow",
                "preview_asset_id": "flow-preview",
                "preview_sha256": preview_sha,
                "reviewer": "reviewer-1",
                "verdict": "pass",
                "summary": "The preview contains a readable Flow label.",
                "findings": [],
                "checked_labels": ["Flow"],
                "reviewed_at": "2026-08-20T00:01:00.000Z",
            }],
        }
        (root / "assets" / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return root

    def test_visual_plan_requires_svg_reference_preflight_and_review_evidence(self) -> None:
        root = self.make_visual_workspace()
        result = VALIDATOR.validate(root)
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["metrics"]["visual_figure_count"], 1)

        manifest_path = root / "assets" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["visual_reviews"] = []
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        missing_review = VALIDATOR.validate(root)
        self.assertFalse(missing_review["passed"])
        self.assertIn("visual.figure.flow-figure.review", {failure["code"] for failure in missing_review["failures"]})

    def test_visual_finalization_rejects_approximate_font_metrics(self) -> None:
        root = self.make_visual_workspace()
        manifest_path = root / "assets" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["visual_preflights"][0]["metric_mode"] = "approximate"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        result = VALIDATOR.validate(root)
        self.assertFalse(result["passed"])
        self.assertIn("visual.figure.flow-figure.preflight", {failure["code"] for failure in result["failures"]})

    def test_mermaid_svg_requires_a_registered_source_hash_binding(self) -> None:
        root = self.make_visual_workspace()
        project_path = root / "project.json"
        project = json.loads(project_path.read_text(encoding="utf-8"))
        project["visual_contract"]["figures"][0]["kind"] = "mermaid"
        project_path.write_text(json.dumps(project, indent=2), encoding="utf-8")

        source_path = root / "assets" / "mermaid" / "flow.mmd"
        source_path.parent.mkdir()
        source_path.write_text("flowchart LR\n  A[Flow] --> B[Publish]\n", encoding="utf-8")
        source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
        manifest_path = root / "assets" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["assets"].insert(0, {
            "id": "flow-mermaid-source",
            "source": "agent",
            "path": "assets/mermaid/flow.mmd",
            "caption": "Mermaid source for the flow diagram",
            "alt_text": "Editable Mermaid source.",
            "provenance": "agent_generated:mermaid-source@11.16.0",
            "licence": "generated_internal",
            "used_in": ["intro"],
            "sha256": source_sha,
        })
        svg = next(entry for entry in manifest["assets"] if entry["id"] == "flow-svg")
        svg["provenance"] = "agent_generated:mermaid-cli@11.16.0"
        svg["derivative_of"] = {
            "asset_id": "flow-mermaid-source",
            "asset_sha256": source_sha,
            "purpose": "rendered_from_mermaid_source",
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        valid = VALIDATOR.validate(root)
        self.assertTrue(valid["passed"], valid["failures"])

        svg["derivative_of"]["asset_sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        invalid = VALIDATOR.validate(root)
        self.assertFalse(invalid["passed"])
        codes = {failure["code"] for failure in invalid["failures"]}
        self.assertIn("assets.derivative.flow-svg.binding", codes)
        self.assertIn("assets.mermaid.flow-svg.source_binding", codes)


if __name__ == "__main__":
    unittest.main()
