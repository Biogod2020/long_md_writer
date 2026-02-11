# Implementation Plan: Image Sourcing Download Acceleration

## Phase 1: Parallel Browser Fallback (Layer 2 提速)
- [x] Task: Refactor `downloader.py` to use multiple tabs for concurrent downloads in Layer 2. c82357d
- [x] Task: Measure performance gain using `tests/test_subagent_sourcing.py`. c82357d

## Phase 1.5: Shotgun Concurrency (策略全并行化)
- [x] Task: Refactor `downloader.py` to fire ALL download methods simultaneously for each candidate. c82357d
- [x] Task: Implement "Winner-Takes-All" logic based on file size comparison. c82357d

## Phase 2: Full Async Download Engine (核心引擎重构)
- [x] Task: Replace `requests` with `httpx.AsyncClient` for non-blocking I/O in Layer 1. f3654be
- [x] Task: Increase Layer 1 concurrency limit from 10 to 30 workers. f3654be

## Phase 3: Original Quality Preservation & Deferred Processing (保真与清理)
- [x] Task: Remove scaling logic from `downloader.py` to ensure only 100% original binaries are saved. f3654be
- [x] Task: Generate intermediate VQA thumbnails on disk after downloading to speed up VLM transfer. f3654be
- [x] Task: Update `vision.py` to use these thumbnails directly. f3654be
- [x] Task: Ensure final delivery uses the Original High-Res binary. f3654be
