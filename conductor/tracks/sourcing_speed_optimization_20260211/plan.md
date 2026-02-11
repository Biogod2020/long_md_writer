# Implementation Plan: Image Sourcing Download Acceleration

## Phase 1: Parallel Browser Fallback (Layer 2 提速)
- [x] Task: Refactor `downloader.py` to use multiple tabs for concurrent downloads in Layer 2. c82357d
- [ ] Task: Measure performance gain using `tests/test_subagent_sourcing.py`.

## Phase 2: Full Async Download Engine (核心引擎重构)
- [ ] Task: Replace `requests` with `httpx.AsyncClient` for non-blocking I/O in Layer 1.
- [ ] Task: Increase Layer 1 concurrency limit from 10 to 30 workers.

## Phase 3: Deferred & Parallel Image Processing (资源处理优化)
- [ ] Task: Parallelize `_resize_image` using `asyncio.to_thread` and run it as a batch after downloads.
- [ ] Task: Final Benchmark: Re-run the 4-target stress test to verify the total time reduction target (>50% faster).
