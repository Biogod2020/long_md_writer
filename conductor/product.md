# Initial Concept

# Product Guide

## Target Audience
The primary users are **Enterprise Content Teams** who need to automate large-scale, high-quality documentation production while maintaining rigorous professional standards.

## Project Goals
- **Automated SOTA Publishing**: Achieve autonomous generation of visually stunning, interactive HTML5 documentation and educational materials.
- **Asset Integrity & Compliance**: Guarantee visual consistency and precise asset sourcing through advanced Visual Quality Assurance (VQA) and the Universal Asset Registry (UAR). Features VLM-driven semantic matching to identify and reuse high-quality local assets before seeking external sources.
- **Workflow Decoupling**: Maintain a strict separation between content logic (Markdown) and presentation logic (HTML). Uses a "Non-Destructive Fulfillment" policy where failed visual assets are preserved as retryable source blocks rather than being replaced by error messages.

## Key Features
- **Multi-Agent Orchestration**: A sophisticated ecosystem of specialized agents (Architect, SME Writer, Asset Critic, etc.) working in parallel to handle complex publishing tasks.
- **Visual Quality Assurance (VQA)**: Automated VLM-based auditing that manages focus-aware cropping, image sourcing, and visual compliance.
- **Context-Aware Generation**: Implementation of "Full-Context Perception" to eliminate AI hallucinations and ensure cross-chapter terminology consistency.
- **Autonomous Remediation & Section QA**: Closed-loop "Critic-Fixer" architecture for both text and visual components. Features a high-precision Universal Patcher with fuzzy matching, scientific rigor auditing, and a multi-stage escalation loop to ensure reliable automated repairs and 100% technical correctness.
- **Modular Asset Management**: A hierarchical "Workspace Mounting" system with Human-in-the-Loop selection, simultaneous multi-pool aggregation, and instant intra-session reuse to maximize asset consistency and production efficiency.
    - **Transactional Parallel Fulfillment**: Orchestrates dozens of visual assets in parallel with a transactional "Working Copy" mechanism. Ensures 100% resume capability and fault tolerance through incremental live-patching and physical asset idempotency.
    - **High-Fidelity State Audit & Breakpoint Resume**: Native integration with LangGraph persistence (AsyncSqliteSaver) combined with a specialized SnapshotManager. Every critical node transition is logically persisted and physically snapshotted, enabling granular "Time Travel" debugging, seamless resumption from process failures, and transparent human-in-the-loop auditing of intermediate artifacts.
    - **Intelligent Sourcing Sub-Agent**: A specialized black-box engine for web-based image discovery. 
        - **Reflection & Self-Correction**: Features an autonomous reflection loop where audit rejections are fed back into query strategy generation to pivot search efforts.
        - **Fidelity-First Pipeline**: Utilizes a "Shotgun" concurrency model (httpx + multi-tab browser) to guarantee 100% original binary quality while using optimized thumbnails for high-speed VLM evaluation.
        - **Atomic Lifecycle Management**: Ensures clean workspaces by automatically removing temporary sourcing fragments while preserving all canonical assets.
    - **Autonomous SVG Sub-Agent**: A dedicated black-box engine for technical illustration.
        - **Reflection Loop**: Implements a self-correcting logic where audit feedback is used to pivot repair strategies via high-precision patching.
        - **Contextual Alignment**: Ensures generated vector graphics remain pedagogically consistent with the surrounding text through full-context perception.

## Frontend & Tooling
- **Dashboard**: Streamlit (for project monitoring and manual intervention).
- **HTML/CSS Processing**: BeautifulSoup4 and lxml (for semantic manipulation of generated outputs).
- **Visual Auditing**: Playwright (for headless browser-based Visual QA and screenshot capture).

## Documentation & Standards
- **Source Format**: Markdown with custom `:::` container extensions for scripts and visual assets.
- **Target Format**: Industrial-grade, responsive HTML5.
