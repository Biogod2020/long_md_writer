# Spec: Modular Asset Workspace Mounting & Intra-Session Reuse

## Overview
Transform the monolithic asset management into a modular "Workspace Mounting" system. This allows users to selectively load domain-specific asset libraries and ensures that agent-generated/sourced assets are instantly reusable within the same session while providing a path for permanent library "promotion."

## Functional Requirements

### 1. Modular Workspace Structure
- **Storage Location**: Assets are organized into named workspaces under `data/asset_workspaces/<workspace_name>/`.
- **Workspace Registry**: Each workspace contains its own `assets.json` (UAR format).
- **Session Directories**:
    - `workspace/<job_id>/agent_generated/`: New SVGs/Mermaid diagrams.
    - `workspace/<job_id>/agent_sourced/`: New Web-sourced images.

### 2. Interactive Mounting & Selection (Phase A/B)
- **Mounting**: User selects one or more workspaces to "mount" at the start of a job.
- **Manual Selection First**: User browses the catalog of mounted workspaces and manually selects assets to include in the "Allowed Pool."
- **Optional AI Suggestions**: After manual selection, the user can choose to let Gemini Flash perform a "Smart Scan" to suggest additional relevant assets (Tier 1 filtering).
- **Mandatory Pool**: Assets provided in `inputs/` are automatically whitelisted and prioritized.

### 3. Intra-Session Reuse Logic
- **Instant Registration**: Any asset produced by the agent (`generated` or `sourced`) is immediately registered in the session's `assets.json`.
- **Unified Aggregation**: The `FulfillmentAgent` processes all potential assets (User-Provided, Session-Produced, and Whitelisted) simultaneously in a single evaluation pool.
- **Prompt-Based Prioritization**: Priority is enforced through the scoring prompt. The LLM is explicitly instructed to favor **User-Provided** and **Whitelisted** assets over **Session-Produced** assets when semantic relevance scores are comparable.
- **90+ Scoring**: Maintain the existing strict semantic scoring for reuse decisions.

### 4. Asset Promotion (Post-Session)
- Mechanism to export/promote high-quality session assets into a permanent `data/asset_workspaces/` folder for future use.

## Technical Architecture
- **UAR Upgrade**: Update `UniversalAssetRegistry` to handle multiple base paths and merged lookups.
- **Path Resolution**: Ensure Markdown/HTML output correctly references assets in their relative physical locations.

## Acceptance Criteria
- [ ] Multiple asset workspaces can be mounted simultaneously.
- [ ] Agent suggests relevant assets from mounted workspaces during initialization.
- [ ] An image generated in Chapter 1 is correctly reused in Chapter 5 of the same session.
- [ ] Newly generated/sourced assets are stored in distinct `agent_generated/` and `agent_sourced/` directories.
- [ ] No duplicate sourcing/generation occurs if an identical intent was already fulfilled in the session.
