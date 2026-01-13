# Spec: Render-Aware Full-Context Editorial QA

## Overview
Upgrade the `EditorialQAAgent` from a passive semantic auditor into a visual-aware, context-integrated autonomous quality gatekeeper. This upgrade ensures that the "visual truth" of the rendered content matches the "semantic intent" of the full book.

## Core Requirements

### 1. Render-Aware Audit (Visual Input)
- The `EditorialCritic` must analyze the **rendered state** of the Markdown section.
- Implementation should use a headless browser (Playwright) or a DOM-to-Image renderer to capture screenshots of the current section.
- The screenshot and/or DOM structure will be passed to the VLM (Gemini) as primary input.

### 2. Full-Context Perception (Semantic Input)
- The Critic must receive the **full raw text** of all previously completed chapters.
- This context allows the agent to verify:
    - Terminology consistency (e.g., ensuring "left ventricle" isn't suddenly called "left heart chamber").
    - Narrative continuity.
    - Consistency between descriptions in Chapter 1 and visual references in Chapter 5.

### 3. Editorial Fixer (Autonomous Action)
- Implement an `EditorialFixer` based on the `MarkdownQA` surgical patching logic.
- The Fixer must be able to:
    - Rewrite text paragraphs to align with images.
    - Adjust `object-position` values in `<img>` tags to fix crop mismatches.
    - Update `alt` text or `figcaption` for accuracy.
    - Swap asset IDs if the wrong image was sourced.

## Technical Architecture
- **Agent Pattern**: Critic-Fixer Loop.
- **Inputs**:
    - Current Section Markdown.
    - Current Section Rendered Screenshot (PNG).
    - Full Preceding Chapters Text.
- **Outputs**:
    - JSON Audit Report.
    - Markdown Search/Replace Patches (if fixes are needed).

## Success Criteria
- [ ] `EditorialQA` correctly identifies a crop mismatch that is only visible in the rendered state.
- [ ] `EditorialQA` identifies a terminology inconsistency by referencing Chapter 1 while auditing Chapter 3.
- [ ] `EditorialFixer` successfully applies a patch to fix a detected issue without breaking Markdown formatting.
