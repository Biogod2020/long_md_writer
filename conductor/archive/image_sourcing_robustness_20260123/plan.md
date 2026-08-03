# Implementation Plan: Image Sourcing Robustness

## Phase 1: Diagnosis & Instrumentation [checkpoint: 080cfcd]
- [x] Task: Instrument `ImageDownloader` for deep diagnosis (98bf02d)
    - [x] Write unit test to verify diagnostic logging capture
    - [x] Implement enhanced logging of response headers, status codes, and error types in `_download_single_requests`
- [x] Task: Conductor - User Manual Verification 'Phase 1: Diagnosis' (Protocol in workflow.md) (080cfcd)

## Phase 2: Hybrid Bypassing Implementation [checkpoint: 3426e56]
- [x] Task: Implement Domain-Aware Referer & Request Logic (36e60b5)
    - [x] Write unit tests for dynamic Referer generation
    - [x] Update `_download_single_requests` to use domain-specific Referer and optimized header sets
- [x] Task: Implement Browser-to-Session Credential Injection (Layer 2) (36e60b5)
    - [x] Write integration test for cookie/UA extraction from DrissionPage
    - [x] Refine `download_candidates` Layer 2 to robustly inject browser state into the concurrent `requests.Session`
- [x] Task: Implement Image Integrity Validation (36e60b5)
    - [x] Write unit tests for file type and size validation
    - [x] Add post-download check to verify magic numbers and minimum file size (>2KB) to filter out block pages
- [x] Task: Conductor - User Manual Verification 'Phase 2: Hybrid Bypassing' (Protocol in workflow.md) (3426e56)

## Phase 3: Final Verification & E2E Stress Test [checkpoint: e92025f]
- [x] Task: Run E2E Stress Test against diverse input intents (Initial Run: 0% Success)
    - [x] Create `scripts/test_image_sourcing_intents.py`
    - [x] Result: 4/4 FAILED. Patterns: Async Conflict, VLM Silent Failure, WAF Blocks.
- [~] Task: 修复压力测试揭示的致命 Pattern (Fix Fatal Patterns)
    - [x] **Pattern 1: Async Conflict**. 重构 `GeminiClient` 调用逻辑。 (0869af7)
    - [x] **Pattern 3: Filename Bug**. 修复 `downloader.py` 中的字面量错误。 (0869af7)
    - [ ] **Pattern 2: WAF Blocks & Resiliency**. 
        - [ ] 实现 **顺位替补机制 (Candidate Rotation)**：如果首选图处理失败，自动尝试 Top 3 列表中的后续图片。
        - [ ] 修复 **Status 567 & Timeout**：增加超时时间，实现“Header 降级”策略。
        - [ ] 确保采购 Agent 具备“部分缺失容忍度”，并在 `failed_directives` 中详细归类报错原因。
- [x] Task: 强化 AI 修复后的再审核逻辑 (Fix Missing Re-Audit Loop) (3426e56)
    - [x] 修改 `src/agents/markdown_qa_agent.py`，确保应用补丁后重置审批状态。
    - [x] 修改 `src/orchestration/workflow_markdown.py` 的路由逻辑，强制修复后回到 Critic 节点。
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Final Verification' (Protocol in workflow.md)
