# Implementation Plan: Agentic ImageSourcing & VLM Concurrency Stress Test

## ⚠️ CRITICAL RISK CONSTRAINT
- **STRICT PROHIBITION**: Do NOT modify `src/core/gemini_client.py`. Any communication logic adjustments must be handled at the Agent/Processor level.

## Phase 1: Refactor to Intent-Driven Sub-Agent (子 Agent 协议重构)
- [x] Task: Establish `fulfill_directive_async` core interface. (Completed with full async/await support).
- [x] Task: Standardize Browser & Resource Management. (Implemented Shotgun Concurrency & multi-tab logic).
- [x] Task: Implement **Self-Correction & Reflection Loop**. (Validated via tests/test_reflection_loop_stress.py).

## Phase 2: VLM Concurrency Stress Test (并发极限探测)
- [x] Task: Identify VLM Concurrency Limit. (Validated Batch 20 stability with Fast-Exit protocol).
- [x] Task: Create `tests/stress_test_vlm_sourcing.py` using "广州市第二中学校服" as the real-world theme. (Verified via tests/test_subagent_sourcing.py).
- [x] Task: Benchmark the Sub-Agent's ability to audit multiple returned results (Batch 20).
- [x] Task: Monitor `geminicli2api-async` logs to identify the "Breaking Point" under multi-task load. (Successfully handled 4 parallel tasks with 80 images).

## Phase 3: SOTA 2.0 Integration & Optimization (全量集成与优化)
- [x] Task: Update `AssetFulfillmentAgent` to treat Sourcing as a pure async black box. (Verified via tests/test_e2e_sota2_sourcing.py).
- [x] Task: Final E2E Validation with 10+ web-image directives to verify the "Reflection -> Pivot -> Audit" chain. (Completed with 100% success rate).
