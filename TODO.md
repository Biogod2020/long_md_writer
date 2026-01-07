# 🧬 Magnum Opus SOTA Upgrade: Tactical TODO List

This document outlines the actionable steps to transform the system into a professional-grade, layered editorial engine with staggered pipelining and universal asset management.

## 🏁 Phase A: Architecture & Protocol Base (Contract-First)
*Goal: Establish the "laws" and "databases" that all agents must follow.*

- [ ] **[Core] Pydantic Model Expansion (`src/core/types.py`)**:
    - [ ] Implement `AssetEntry` and `UniversalAssetRegistry` (UAR) models.
    - [ ] Implement `GhostBuffer` and `SkeletonEntry` for incremental context.
    - [ ] Add `ProcessingStatus` enum (`DRAFT`, `LINTED`, `AUDITED`, `RENDERED`, `VERIFIED`).
    - [ ] Update `SectionInfo` to include `namespace` and `status` fields.
- [ ] **[Protocol] Formal Directive & Component Schemas**:
    - [ ] Create `src/assets/schemas/directives.json` (Specs for `:::visual` and `:::script`).
    - [ ] Create `src/assets/schemas/components.json` (The whitelist of supported interactive widgets).
- [ ] **[Tools] Asset & Namespace Management**:
    - [ ] Develop `AssetIndexerAgent`: Scan `inputs/` at start, label user assets via Vision API, and populate UAR.
    - [ ] Develop `NamespaceManager`: A Python utility to automatically inject unique ID prefixes (e.g., `s1-`) into the Manifest.
- [ ] **[Agent] Architect Decoupling**:
    - [ ] Refactor `ArchitectAgent` prompt: Focus on "Logic + Intent" only; offload technical implementation to TechSpec.

## 🖋️ Phase B: Layered Editorial Workflow (Markdown Layer)
*Goal: Implement concern separation at the semantic level.*

- [ ] **[Agent] Pure Content Writer**:
    - [ ] Refactor `WriterAgent`: Focus strictly on narrative depth and SME knowledge.
    - [ ] Use simple placeholders like `[RESERVED: visual intent="..."]`.
- [ ] **[New Agent] Visual Decorator**:
    - [ ] Create agent to scan MD, match `user_asset_registry`, and inject `:::visual {json}` blocks.
- [ ] **[New Agent] Script Decorator**:
    - [ ] Create agent to inject `:::script {json}` blocks for animation and interaction protocols.
- [ ] **[Agent] Editorial QA (The Editor-in-Chief)**:
    - [ ] Upgrade `MarkdownQAAgent` to validate the multi-layer MD against the `Manifest` and `GhostBuffer`.

## 🖼️ Phase C: Asset-First Loop (Shift-Left VQA)
*Goal: Generate and verify visuals BEFORE HTML conversion.*

- [ ] **[Flow] Asset Fulfillment Loop**:
    - [ ] Create a micro-loop: Extract `:::visual` -> Run SVG Gen/Image Sourcing -> Update UAR.
- [ ] **[New Agent] Asset Critic (Vision-based)**:
    - [ ] Perform isolated VQA on generated SVGs and sourced images against their MD descriptions.
- [ ] **[Agent] Transformer Refactor**:
    - [ ] Simplify `TransformerAgent`: It should only perform "Token Replacement" (MD Directives -> HTML Components) based on UAR verified paths.

## ⚡ Phase D: Staggered Pipeline & Ghost Buffer
*Goal: Optimize for speed without losing consistency.*

- [ ] **[Orchestration] LangGraph Parallelization**:
    - [ ] Update `workflow.py` to support parallel edges for `Writer(N+1)` and `Transform(N)`.
- [ ] **[Core] Skeleton Management**:
    - [ ] Implement ghost buffer injection: Ensure `Transformer(N)` sees verified `sec-(N-1)` code and verified `1...N-2` skeletons.
- [ ] **[Logic] State-Gating Controllers**:
    - [ ] Implement logic to prevent `Transformer` from starting until `Markdown QA` issues a `logic_verified` status.

## 🕵️ Phase E: Advanced Verification (Multi-modal VQA)
*Goal: Audit interactions and visual "seams".*

- [ ] **[New Agent] JS Probe (Playwright MCP)**:
    - [ ] Implement browser-based auditing: Listen for `console.error` and `network-failed` (404s).
    - [ ] Verify animation triggers via DOM state inspection.
- [ ] **[Agent] Seam Auditor (VQA Expansion)**:
    - [ ] Add "Overlap Snapshot" logic: Capture screenshots of section junctions to ensure style continuity.
- [ ] **[Agent] Contrast Enforcer**:
    - [ ] Programmatic WCAG contrast check in `DesignTokensAgent` before JSON output.

## 📦 Phase F: Production Polishing
- [ ] **[New Agent] Distiller Agent**:
    - [ ] Logic for single-file inlining, asset versioning, and SEO JSON-LD generation.
- [ ] **[UI] Streamlit Dashboard Update**:
    - [ ] Add a real-time "Pipeline Gantt Chart" or progress trackers for individual sections.
