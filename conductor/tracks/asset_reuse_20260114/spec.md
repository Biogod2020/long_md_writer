# Spec: Intelligent Asset Reuse and Deduplication

## Overview
Enhance the Asset Fulfillment pipeline to intelligently identify and reuse existing high-quality assets from the Universal Asset Registry (UAR). The system must balance the benefit of reusing assets (consistency, efficiency) with the risk of **visual repetition** in the final article.

## Functional Requirements

### 1. Contextual Asset Scoring (Relevance)
- The `AssetFulfillmentAgent` must implement a strict scoring mechanism (0-100) to evaluate existing assets against a new `:::visual` intent.
- **Score >= 90**: Candidate for reuse.
- **Score < 90**: Proceed to new asset generation/sourcing.

### 2. Usage Frequency Awareness (Repetition Control)
- The agent must track how many times a specific asset has already been used in the current document.
- **Deduplication Logic**:
    - If a high-scoring asset (Score >= 90) has *already* been used nearby (e.g., in the same chapter or previous N paragraphs), the agent should consider:
        - **Is it necessary to show it again?** (e.g., "As shown in the diagram above...")
        - **Should it be suppressed?** (If it adds no new value).
        - **Should a NEW variation be created?** (To avoid visual fatigue).
    - If the repetition is justified (e.g., a reference icon, a recurring character, or a comparison table), reuse is **ALLOWED**.

### 3. Execution Logic
- **Reuse**: Inject the existing `asset_id` into the Markdown.
- **Creation**: Generate a new asset if the reuse score is low OR if reusing the existing one would cause negative visual repetition.

## Acceptance Criteria
- [ ] System reuses an asset ID if the semantic match is > 90/100.
- [ ] System allows the same asset ID to appear multiple times if the context justifies it (e.g., comparison).
- [ ] System avoids creating a *new file* for an image that already exists in the library (file-level deduplication).
- [ ] System avoids *excessive visual repetition* in the rendered output (e.g., not showing the exact same large hero image twice in 500 words without cause).

## Out of Scope
- Cross-project deduplication.
