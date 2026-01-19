# Plan: Modular Asset Workspace Mounting & Intra-Session Reuse

This plan follows the TDD and verification protocols defined in `conductor/workflow.md`.

## Phase 1: Modular UAR & Path Refactoring [checkpoint: 94183ee]

- [~] Task: Create `tests/test_modular_uar.py` to verify multi-workspace loading and merged lookups.
- [ ] Task: Refactor `UniversalAssetRegistry` to support mounting multiple `assets.json` files from `data/asset_workspaces/`.
- [ ] Task: Standardize output paths to include `agent_generated/` and `agent_sourced/` in `AssetFulfillmentAgent`.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Modular UAR & Path Refactoring' (Protocol in workflow.md) 94183ee

## Phase 2: Interactive Manual Selection & Optional AI Discovery [checkpoint: 64fba48]

- [~] Task: Create `tests/test_asset_discovery_selection.py` for manual and AI-assisted selection logic.
- [ ] Task: Implement Terminal/CLI interface for browsing and manually selecting assets from mounted workspaces.
- [ ] Task: Implement optional Tier 1 "Broad Search" using Gemini Flash to suggest additional assets.
- [x] Task: Conductor - User Manual Verification 'Phase 2: Interactive Manual Selection & Optional AI Discovery' (Protocol in workflow.md) 64fba48

## Phase 3: Unified Asset Aggregation & Prompt Prioritization

- [ ] Task: Create `tests/test_intra_session_reuse.py` to verify unified aggregation logic.
- [ ] Task: Update `AssetFulfillmentAgent` to register new assets immediately into the session registry.
- [ ] Task: Update `_decide_fulfillment_strategy` to aggregate all asset types into a single candidate list.
- [ ] Task: Enhance the scoring prompt in `_calculate_reuse_score` to prioritize User-Provided/Whitelisted assets.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Unified Asset Aggregation & Prompt Prioritization' (Protocol in workflow.md)

## Phase 4: Integration & Promotion Workflow

- [ ] Task: End-to-end test: Mount a workspace, select assets, generate new ones, and verify multi-chapter reuse.
- [ ] Task: Implement a prototype "Promotion" command to copy session assets to a workspace.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Integration & Promotion Workflow' (Protocol in workflow.md)
