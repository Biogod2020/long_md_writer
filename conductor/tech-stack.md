# Technology Stack

## Core Engine
- **Language**: Python 3.x
- **Orchestration**: LangGraph (for multi-agent state management and complex workflows).
- **Persistence**: Native SQLite-based checkpointing (AsyncSqliteSaver) for robust state recovery and thread-safe multi-session management.
- **Data Validation**: Pydantic (for strictly typed inter-agent communication and configuration).

## Agent Architecture
- **Framework**: Custom multi-agent ecosystem utilizing specialized roles (Architect, SME Writer, Asset Critic, Editorial QA) and intent-driven sub-agents (Sourcing, SVG).
- **Communication**: Asynchronous event-driven architecture using `asyncio`.
- **Network Engine**: `httpx` (AsyncClient) for high-performance non-blocking I/O and intelligent connection pooling targeting `geminicli2api-async` (8888 port).
- **LLM Protocol**: Google Native Gemini API Protocol (`/v1beta/models/...:generateContent`).
  - Native Multimodal `inline_data` support.
  - Native JSON Schema enforcement.
  - **Robust JSON Parsing**: Advanced error-correction for malformed LLM outputs, including unescaped LaTeX backslashes and illegal whitespace characters.
  - VLM-driven semantic candidate selection for local asset matching.
  - **High-Precision Patching**: Fuzzy text matching, indentation-agnostic patching logic, and a **multi-stage escalation retry loop** with rich error feedback and full-code fallback.
  - **Scientific Rigor Auditing**: VLM-driven visual verification focusing on technical correctness, mathematical alignment, and standard scientific conventions.
  - **Transactional Resilience**: Atomic file operations and breakpoint resume for long-running asset pipelines.
  - "Thinking" token (thoughts) capture and state integration.
  - Intelligent connection pooling and exponential backoff for network resilience.
  - High-concurrency parallel fulfillment with semaphore-based rate limiting.
  - **Shotgun Sourcing Strategy**: Massive parallelism (up to 30 concurrent tasks) across multiple download methods (Direct, Browser-based, JS Stealth Fetch) with **First-Win Race Condition** and winner-takes-all selection.
  - **Hierarchical VLM Selection**: A multi-tiered competitive audit process (Elite Pass + 10-to-2-to-1 Fallback) to ensure the highest-fidelity asset capture.
  - **Anti-Interference Browser Control**: Implementation of Proxy Armor (NO_PROXY enforcement) and Manual Port Cycling to bypass environment-level network interception.
  - **Fidelity-First Asset Pipeline**:
    - In-memory/On-disk hybrid processing for 100% original binary preservation.
    - Pre-generated VQA thumbnails for low-latency VLM transfer.
    - Atomic cleanup of candidate fragments post-sourcing.

## Frontend & Tooling
- **Dashboard**: Streamlit (for project monitoring and manual intervention).
- **HTML/CSS Processing**: BeautifulSoup4 and lxml (for semantic manipulation of generated outputs).
- **Visual Auditing**: Playwright (for headless browser-based Visual QA and screenshot capture).
- **Image Intelligence**: `Pillow` (PIL) for high-fidelity image manipulation, format normalization, and memory-safe scaling.

## Documentation & Standards
- **Source Format**: Markdown with custom `:::` container extensions for scripts and visual assets.
- **SSOT Lifecycle**: Employs a physical merging strategy (`final_full.md`) with traceability markers (`<!-- SECTION: xxx -->`) for cross-chapter global QA and automated non-destructive sync.
- **Target Format**: Industrial-grade, responsive HTML5.
