# Track Specification: SVG Sub-Agent Decoupling & Enhancement

## Overview
Currently, the SVG generation, visual auditing, and patch-based repair logic are tightly coupled within the `AssetFulfillmentAgent`. This track aims to refactor this logic into a dedicated, black-box sub-agent package (`src/agents/svg_generation/`), mirroring the successful architecture of the `ImageSourcingAgent`. This refactoring will simplify the main orchestrator, improve maintainability, and introduce a formal "Reflection Loop" to enhance the success rate of automated SVG repairs.

## Functional Requirements
1.  **New Sub-Agent Package**: 
    - Create a new directory and package at `src/agents/svg_generation/`.
    - Implement a core `SVGAgent` class.
2.  **Black-Box Interface**:
    - Expose a single asynchronous method `fulfill_directive_async(directive, state)` that handles the entire SVG lifecycle (Generate -> Audit -> Repair).
3.  **Logic Migration & Archival**:
    - Migrate existing SVG generation and repair logic from `src/agents/asset_management/processors/svg.py` and `fulfillment.py` to the new package.
    - Archive the original files (e.g., `svg.py.bak`) to ensure a safe recovery path during development.
4.  **Reflection Loop Implementation**:
    - Enhance the repair cycle by implementing a formal "Reflection Loop".
    - Rejection feedback from the VLM visual audit must be explicitly fed back into the strategy generator to pivot keywords or structural constraints for the next repair attempt.
5.  **Orchestrator Update**:
    - Update `AssetFulfillmentAgent` to remove inline SVG logic and instead delegate all SVG tasks to the new `SVGAgent`.

## Non-Functional Requirements
- **Consistency**: Maintain architectural symmetry with the `ImageSourcingAgent`.
- **Maintainability**: Centralize all SVG-specific logic, prompts, and strategies.
- **Performance**: Ensure the sub-agent operates efficiently within the existing asynchronous parallel fulfillment pipeline.

## Acceptance Criteria
- [ ] `AssetFulfillmentAgent` successfully delegates `GENERATE_SVG` tasks to the new `SVGAgent`.
- [ ] The `SVGAgent` internally manages the Generate-Audit-Repair loop.
- [ ] The Reflection Loop correctly utilizes audit feedback to improve successive SVG versions.
- [ ] Existing SVG generation workflows remain functional (regression testing).
- [ ] Original processor files are properly archived.

## Out of Scope
- Refactoring Mermaid or Web Search logic (these will remain as-is for this track).
- Major changes to the underlying `GeminiClient` or `UniversalAssetRegistry`.
