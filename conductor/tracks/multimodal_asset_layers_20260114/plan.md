# Plan: Multimodal Intent-Layered Asset Management

This plan follows the TDD and verification protocols defined in `conductor/workflow.md`.

## Phase 1: Visual Base & Intent Categorization [checkpoint: ada66ca]

- [x] Task: Create `tests/test_modular_asset_scoring.py` to verify intent-based filtering. 87e5c6f
- [x] Task: Update `AssetEntry` and `AssetIndexerAgent` to support `priority` tags and Base64 caching. 87e5c6f
- [x] Task: Implement `inputs/mandatory/` directory scanning logic. 87e5c6f
- [x] Task: Conductor - User Manual Verification 'Phase 1: Visual Base & Intent Categorization' (Protocol in workflow.md) ada66ca

## Phase 2: Multimodal Architecting (Planning)

- [ ] Task: Write tests for `ArchitectAgent` visual assignment (ensuring Mandatory assets appear in Manifest).
- [ ] Task: Upgrade `ArchitectAgent._build_prompt_parts` to add Base64 imagery for Mandatory assets while keeping all other context inputs intact.
- [ ] Task: Update `Manifest` model to include `assigned_assets` in section metadata.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Multimodal Architecting (Planning)' (Protocol in workflow.md)

## Phase 3: Multimodal Writing Loop (Execution)

- [ ] Task: Write tests for `WriterAgent`看图写作 (verifying visual adherence in generated text).
- [ ] Task: Upgrade `WriterAgent._build_multimodal_prompt` to add targeted chapter-assigned imagery while keeping all other context inputs intact.
- [ ] Task: Implement "Visual Contextualization" instructions in the Writer's System Prompt.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Multimodal Writing Loop (Execution)' (Protocol in workflow.md)

## Phase 4: Enforcement & SOTA Verification

- [ ] Task: Write tests for `EditorialQA` coverage audit (detecting missing Mandatory assets).
- [ ] Task: Implement Mandatory Asset Validator in `EditorialQAAgent`.
- [ ] Task: End-to-end test: Full run with one mandatory asset, verify it appears in the final text and passes QA.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Enforcement & SOTA Verification' (Protocol in workflow.md)
