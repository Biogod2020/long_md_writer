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

    def test_remote_http_image_fails(self) -> None:
        article = self.valid_article().replace(
            "This deterministic article",
            "![remote](https://example.com/x.png)\nThis deterministic article",
        )
        root = self.make_workspace(article_text=article)
        result = VALIDATOR.validate(root)
        self.assertFalse(result["passed"])
        self.assertIn("assets.no_remote_images", {failure["code"] for failure in result["failures"]})

    def test_svg_labels_require_visible_text_but_accept_equivalent_aria_typography(self) -> None:
        root = self.make_workspace(article_text=self.valid_article())
        svg_path = root / "formula.svg"
        svg_path.write_text(
            """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 80">
<text x="10" y="40" aria-label="QKᵀ/√dₖ">QK<tspan baseline-shift="super">T</tspan>/√d<tspan baseline-shift="sub">k</tspan></text>
<text x="0" y="0" opacity="0" fill="none">hidden exact</text>
<text x="10" y="70" aria-label="unrelated exact">visible mismatch</text>
</svg>""",
            encoding="utf-8",
        )
        labels, error = VALIDATOR.svg_text_labels(svg_path)
        self.assertIsNone(error)
        self.assertIn("QKᵀ/√dₖ", labels)
        self.assertNotIn("hidden exact", labels)
        self.assertNotIn("unrelated exact", labels)

    def test_malformed_chunk_fails(self) -> None:
        root = self.make_workspace(article_text=self.valid_article().replace("<!-- longwriter:chunk intro-01:end -->", ""))
        result = VALIDATOR.validate(root)
        self.assertFalse(result["passed"])
        self.assertIn("article.chunk_markers", {failure["code"] for failure in result["failures"]})

    def test_quality_ceiling_rejects_overshoot_and_long_sentences(self) -> None:
        root = self.make_workspace(article_text=self.valid_article())
        project_path = root / "project.json"
        project = json.loads(project_path.read_text(encoding="utf-8"))
        project["quality_contract"].update({
            "maximum_section_ratio": 1.1,
            "maximum_total_ratio": 1.1,
            "long_sentence_chars": 20,
            "maximum_long_sentence_ratio": 0.0,
        })
        project_path.write_text(json.dumps(project, indent=2), encoding="utf-8")
        result = VALIDATOR.validate(root)
        codes = {failure["code"] for failure in result["failures"]}
        self.assertIn("article.section.intro.maximum_length", codes)
        self.assertIn("article.maximum_total_length", codes)
        self.assertIn("article.section.intro.long_sentences", codes)

    def test_image_search_contract_requires_hash_bound_candidate_receipts(self) -> None:
        root = self.make_workspace(article_text=self.valid_article())
        project_path = root / "project.json"
        project = json.loads(project_path.read_text(encoding="utf-8"))
        project["research_contract"] = {"minimum_image_searches": 1, "minimum_image_candidates": 1}
        project_path.write_text(json.dumps(project, indent=2), encoding="utf-8")
        missing = VALIDATOR.validate(root)
        missing_codes = {failure["code"] for failure in missing["failures"]}
        self.assertIn("research.image_search_count", missing_codes)
        self.assertIn("research.image_candidate_count", missing_codes)

        candidate = {
            "source_id": "candidate-1",
            "rank": 1,
            "title": "ECG placement",
            "image_url": "https://images.example.test/ecg.png",
            "source_page_url": "https://example.test/ecg",
            "width": 1200,
            "height": 800,
            "score": 80,
            "domain_hint": "good",
        }
        payload = {"query": "ECG placement", "provider": "bing_images", "candidates": [candidate]}
        receipt = {
            "id": "image-search-one",
            **payload,
            "result_sha256": hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "searched_at": "2026-08-27T00:00:00.000Z",
        }
        manifest_path = root / "assets" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["image_searches"] = [receipt]
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        valid = VALIDATOR.validate(root)
        self.assertTrue(valid["passed"], valid["failures"])

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
                "number": 1,
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
                "reviewer_role": "human_visual_review",
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

    def test_photo_figure_accepts_registered_raster_and_still_rejects_remote_urls(self) -> None:
        article = self.valid_article().replace(
            "This deterministic article",
            "![ECG machine](assets/photos/ecg.png)\n图1 床旁心电图机。\nThis deterministic article",
        )
        root = self.make_workspace(article_text=article)
        project_path = root / "project.json"
        project = json.loads(project_path.read_text(encoding="utf-8"))
        project["visual_contract"] = {
            "schema_version": 1,
            "figure_start": 1,
            "minimum_figures": 1,
            "required_sections": ["intro"],
            "figures": [{
                "id": "ecg-machine",
                "number": 1,
                "section_id": "intro",
                "kind": "photo",
                "purpose": "Show a real electrocardiograph.",
                "required_labels": ["ECG"],
                "review_required": True,
            }],
        }
        project_path.write_text(json.dumps(project, indent=2), encoding="utf-8")
        photo_path = root / "assets" / "photos" / "ecg.png"
        photo_path.parent.mkdir()
        photo_path.write_bytes(b"\x89PNG\r\n\x1a\nphoto")
        preview_path = root / "assets" / "reviews" / "ecg-preview.png"
        preview_path.parent.mkdir()
        preview_path.write_bytes(b"\x89PNG\r\n\x1a\npreview")
        photo_sha = hashlib.sha256(photo_path.read_bytes()).hexdigest()
        preview_sha = hashlib.sha256(preview_path.read_bytes()).hexdigest()
        (root / "assets" / "manifest.json").write_text(json.dumps({
            "schema_version": 2,
            "assets": [
                {
                    "id": "ecg-photo",
                    "source": "web_image",
                    "path": "assets/photos/ecg.png",
                    "caption": "ECG machine",
                    "alt_text": "A bedside electrocardiograph.",
                    "provenance": "web_image:https://images.example.test/ecg.png",
                    "licence": "source_url",
                    "used_in": ["intro"],
                    "sha256": photo_sha,
                    "visual_plan_id": "ecg-machine",
                },
                {
                    "id": "ecg-preview",
                    "source": "tool",
                    "path": "assets/reviews/ecg-preview.png",
                    "caption": "Preview evidence",
                    "alt_text": "A raster preview.",
                    "provenance": "derived:photo-preflight",
                    "licence": "generated_internal",
                    "used_in": [],
                    "sha256": preview_sha,
                    "derivative_of": {
                        "asset_id": "ecg-photo",
                        "asset_sha256": photo_sha,
                        "purpose": "photo-preview",
                    },
                },
            ],
            "visual_preflights": [{
                "id": "preflight-photo",
                "asset_id": "ecg-photo",
                "asset_sha256": photo_sha,
                "visual_plan_id": "ecg-machine",
                "preview_asset_id": "ecg-preview",
                "preview_sha256": preview_sha,
                "metric_mode": "photo",
                "renderer": "identity-png",
                "passed": True,
                "issues": [],
                "warnings": [],
                "created_at": "2026-08-20T00:00:00.000Z",
            }],
            "visual_reviews": [{
                "id": "review-photo",
                "asset_id": "ecg-photo",
                "asset_sha256": photo_sha,
                "visual_plan_id": "ecg-machine",
                "preflight_id": "preflight-photo",
                "preview_asset_id": "ecg-preview",
                "preview_sha256": preview_sha,
                "reviewer": "author-thread:test",
                "reviewer_role": "author_visual_check",
                "verdict": "pass",
                "summary": "The preview shows a readable ECG machine.",
                "findings": [],
                "checked_labels": ["ECG"],
                "reviewed_at": "2026-08-20T00:01:00.000Z",
            }],
        }, indent=2), encoding="utf-8")
        result = VALIDATOR.validate(root)
        self.assertTrue(result["passed"], result["failures"])

        remote = self.valid_article().replace(
            "This deterministic article",
            "![hotlink](https://images.example.test/ecg.png)\nThis deterministic article",
        )
        remote_root = self.make_workspace(article_text=remote)
        remote_result = VALIDATOR.validate(remote_root)
        self.assertFalse(remote_result["passed"])
        self.assertIn("assets.no_remote_images", {failure["code"] for failure in remote_result["failures"]})

    def test_visual_contract_enforces_numbering_minimum_and_section_coverage(self) -> None:
        root = self.make_visual_workspace()
        project_path = root / "project.json"
        project = json.loads(project_path.read_text(encoding="utf-8"))
        project["visual_contract"].update({
            "figure_start": 1,
            "minimum_figures": 1,
            "required_sections": ["intro"],
        })
        project["visual_contract"]["figures"][0]["number"] = 2
        project_path.write_text(json.dumps(project, indent=2), encoding="utf-8")
        result = VALIDATOR.validate(root)
        codes = {failure["code"] for failure in result["failures"]}
        self.assertIn("project.visual_figure.0", codes)
        self.assertIn("project.visual_minimum_count", codes)
        self.assertIn("project.visual_required_sections", codes)

    def test_visual_finalization_rejects_approximate_font_metrics(self) -> None:
        root = self.make_visual_workspace()
        manifest_path = root / "assets" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["visual_preflights"][0]["metric_mode"] = "approximate"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        result = VALIDATOR.validate(root)
        self.assertFalse(result["passed"])
        self.assertIn("visual.figure.flow-figure.preflight", {failure["code"] for failure in result["failures"]})

    def test_visual_review_identity_cannot_claim_an_author_check_as_independent(self) -> None:
        root = self.make_visual_workspace()
        manifest_path = root / "assets" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["visual_reviews"][0]["reviewer_role"] = "author_visual_check"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        result = VALIDATOR.validate(root)
        self.assertFalse(result["passed"])
        self.assertIn("assets.visual_review.0.identity", {failure["code"] for failure in result["failures"]})

    def test_schema_v2_requires_publication_width_and_structured_visual_quality(self) -> None:
        root = self.make_visual_workspace()
        project_path = root / "project.json"
        project = json.loads(project_path.read_text(encoding="utf-8"))
        criterion = "The flow label is visible and names the depicted process."
        project["visual_contract"]["schema_version"] = 2
        project["visual_contract"]["figures"][0]["design_brief"] = {
            "figure_type": "process",
            "publication_width": "double_column",
            "scientific_claim": "The figure depicts a named flow.",
            "scientific_checks": [criterion],
            "reading_order": ["Flow"],
        }
        project_path.write_text(json.dumps(project, indent=2), encoding="utf-8")

        manifest_path = root / "assets" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        review = manifest["visual_reviews"][0]
        review["reviewer"] = "independent-thread:test:config-test"
        review["reviewer_role"] = "independent_visual_review"
        review["scientific_checks"] = [{
            "criterion": criterion,
            "verdict": "pass",
            "evidence": "The retained preview visibly contains the Flow label.",
        }]
        review["design_checks"] = {key: "pass" for key in VALIDATOR.DESIGN_CHECK_KEYS}
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        valid = VALIDATOR.validate(root)
        self.assertTrue(valid["passed"], valid["failures"])

        del project["visual_contract"]["figures"][0]["design_brief"]["publication_width"]
        project_path.write_text(json.dumps(project, indent=2), encoding="utf-8")
        missing_width = VALIDATOR.validate(root)
        self.assertIn("project.visual_figure.0", {failure["code"] for failure in missing_width["failures"]})

        project["visual_contract"]["figures"][0]["design_brief"]["publication_width"] = "double_column"
        project_path.write_text(json.dumps(project, indent=2), encoding="utf-8")
        review["design_checks"]["composition_spacing"] = "fail"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        failed_rubric = VALIDATOR.validate(root)
        self.assertIn("assets.visual_review.0.quality_rubric", {failure["code"] for failure in failed_rubric["failures"]})

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
