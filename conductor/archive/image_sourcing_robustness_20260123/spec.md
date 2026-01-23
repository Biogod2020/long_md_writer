# Specification: Image Sourcing Robustness & Anti-Crawler Bypassing

## 1. Overview
Identify and fix the root causes of download failures in `src/agents/image_sourcing/`. The goal is to achieve near-100% sourcing success by implementing a hybrid bypassing strategy that leverages both real browser state and high-speed protocol mimicry.

## 2. Functional Requirements
- **Deep Diagnosis Interface**: Enhanced logging in `ImageDownloader` to capture full response headers and status codes when a download fails.
- **Intent-Driven Stress Testing**:
    - Implement a testing suite that simulates diverse user "visual intents" (e.g., "high-tech lab", "anatomical diagram", "historical medical device").
    - Verify the entire pipeline: Intent -> Query Gen -> Search -> Download -> VLM Selection -> Final Fulfillment.
- **Pattern-Based Failure Analysis**:
    - Categorize sourcing failures into root-cause patterns: "Semantic Mismatch", "Query Hallucination", "Network 403/429", "Payload Integrity Failure".
    - Automatically summarize failure patterns at the end of stress tests to guide systematic technical fixes.
- **Hybrid Sourcing Strategy**:
    - Use **DrissionPage** to navigate to the target image domain, bypassing initial challenges (Cloudflare, JS-fingerprinting).
    - Extract session credentials (Cookies, User-Agent, TLS hints) from the browser.
    - Inject these credentials into a persistent `requests.Session` for concurrent, high-speed downloading.
- **Intelligent Fallback Loop**: 
    - If a protocol-level request (Layer 1) returns 403/429, automatically trigger a browser-based session refresh (Layer 2).
    - Ensure dynamic `Referer` headers are set to match the target domain to bypass hotlink protection.
- **Success Verification**: Implement a validation step that checks file size and magic numbers to ensure the downloaded file is a valid image and not a block-page HTML.

## 3. Acceptance Criteria
- **100% Sourcing Target**: All visual directives requiring `SEARCH_WEB` must result in a valid image in the `agent_sourced` directory.
- **Zero Redundancy**: Avoid duplicate downloads; ensure the UAR is updated with the correct physical path.
- **Transparent Debugging**: `trace.json` must clearly show the transition from "Requests Failed" to "Browser Auth Succeeded" to "Download Complete".

## 4. Out of Scope
- Changing the image search engine (staying with Google Image Search).
- Permanent storage of images in external cloud providers (staying local to workspace).
