# Specification: WebSourcing Hierarchical Audit & Deadlock Prevention

## 1. Overview
This track aims to enhance the reliability and quality of the web-based image sourcing pipeline. It introduces a two-layer hierarchical VLM (Vision-Language Model) audit process to ensure high-fidelity asset selection and implements a robust "Timeout-based Reset" strategy to eliminate browser deadlocks while preserving session integrity to avoid Google CAPTCHA triggers.

## 2. Functional Requirements

### 2.1 Hierarchical VLM Audit (Two-Layer Selection)
*   **Result Shuffling**: All raw search results must be shuffled before batching to ensure diversity in the initial selection pool.
*   **Batching & Threshold**:
    *   Results are processed in groups of **10**.
    *   If fewer than 10 results are found, the system must perform retries or secondary queries until the 10-item threshold is met.
*   **Layer 1 Audit (10-to-2)**:
    *   The VLM analyzes the group of 10 and selects the **top 2** candidates.
    *   Criteria: Semantic relevance to intent, image resolution/clarity, technical/logical accuracy, and aesthetic professionalism.
*   **Layer 2 Audit (2-to-1)**:
    *   The VLM performs a final comparative audit on the 2 finalists to select the single best asset for fulfillment.

### 2.2 Deadlock Prevention & Download Stability
*   **Strategy: Timeout-based Reset**:
    *   Implement strict, multi-tier timeouts for navigation, element interaction, and physical file download.
    *   Implement an "Automatic Tab Recycling" mechanism to recover from hung pages without restarting the entire browser process.
*   **Safety Constraint (Anti-CAPTCHA)**:
    *   **Prohibited Action**: Do not modify or clear authentication-related cookies, headers, or local storage.
    *   Avoid high-frequency process-level restarts that might trigger Google's bot detection (Singleton stability).

## 3. Non-Functional Requirements
*   **Performance**: The two-layer audit should add no more than 15% latency compared to the current single-layer selection.
*   **Robustness**: 100% recovery rate from individual page hangs via tab recycling.

## 4. Acceptance Criteria
- [ ] Search results are shuffled and batched into groups of 10.
- [ ] VLM successfully performs a 10-to-2 selection followed by a 2-to-1 final selection.
- [ ] A simulated "hanging download" is successfully interrupted by a timeout and the browser tab is recycled.
- [ ] Browser session remains valid (no authentication loss) throughout multiple fulfillment cycles.

## 5. Out of Scope
*   Replacing the underlying `ImageSourcingAgent` architecture (this is a refactor of its internal selection and stability logic).
*   Automatic CAPTCHA solving (the goal is to *avoid* triggering them).
