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
- **Autonomous Remediation & Section QA**: Closed-loop "Critic-Fixer" architecture for both text and visual components. Implements per-section AI self-correction followed by a centralized high-performance parallel fulfillment phase.
- **Modular Asset Management**: A hierarchical "Workspace Mounting" system with Human-in-the-Loop selection, simultaneous multi-pool aggregation, and instant intra-session reuse to maximize asset consistency and production efficiency.
- **Parallel Fulfillment Pipeline**: Orchestrates dozens of visual assets (SVG, Mermaid, sourced images) in parallel at the end of the writing phase, with batch human intervention for quality failures.