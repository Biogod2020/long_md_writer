# Plan: Multimodal Intent-Layered Asset Management

This plan follows the TDD and verification protocols defined in `conductor/workflow.md`.

## Phase 1: Visual Base & Intent Categorization [checkpoint: ada66ca]

- [x] Task: Create `tests/test_modular_asset_scoring.py` to verify intent-based filtering. 87e5c6f
- [x] Task: Update `AssetEntry` and `AssetIndexerAgent` to support `priority` tags and Base64 caching. 87e5c6f
- [x] Task: Implement `inputs/mandatory/` directory scanning logic. 87e5c6f
- [x] Task: Conductor - User Manual Verification 'Phase 1: Visual Base & Intent Categorization' (Protocol in workflow.md) ada66ca

## Phase 2: Multimodal Architecting (Planning) [checkpoint: c53d5f8]

- [x] Task: Write tests for `ArchitectAgent` visual assignment (ensuring Mandatory assets appear in Manifest.) fca7b69
- [x] Task: Upgrade `ArchitectAgent._build_prompt_parts` to add Base64 imagery for Mandatory assets while keeping all other context inputs intact. fca7b69
- [x] Task: Update `Manifest` model to include `assigned_assets` in section metadata. fca7b69
- [x] Task: Conductor - User Manual Verification 'Phase 2: Multimodal Architecting (Planning)' (Protocol in workflow.md) c53d5f8

## Phase 3: Multimodal Writing Loop (Execution) [checkpoint: 8f235ca]

- [x] Task: Write tests for `WriterAgent`看图写作 (verifying visual adherence in generated text.) c1418bd
- [x] Task: Upgrade `WriterAgent._build_multimodal_prompt` to add targeted chapter-assigned imagery while keeping all other context inputs intact. c1418bd
- [x] Task: Implement "Visual Contextualization" instructions in the Writer's System Prompt. c1418bd
- [x] Task: Conductor - User Manual Verification 'Phase 3: Multimodal Writing Loop (Execution)' (Protocol in workflow.md) 8f235ca

## Phase 4: Enforcement & SOTA Verification

- [x] Task: Write tests for `EditorialQA` coverage audit (detecting missing Mandatory assets.) 85ba880
- [x] Task: Implement Mandatory Asset Validator in `EditorialQAAgent`. 85ba880
- [ ] Task: End-to-end test: Full run with one mandatory asset, verify it appears in the final text and passes QA.
- [~] Task: Conductor - User Manual Verification 'Phase 4: Enforcement & SOTA Verification' (Protocol in workflow.md)
