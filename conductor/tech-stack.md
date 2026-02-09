# Technology Stack

## Core Engine
- **Language**: Python 3.x
- **Orchestration**: LangGraph (for multi-agent state management and complex workflows).
- **Persistence**: Native SQLite-based checkpointing (AsyncSqliteSaver) for robust state recovery and thread-safe multi-session management.
- **Data Validation**: Pydantic (for strictly typed inter-agent communication and configuration).

## Agent Architecture
- **Framework**: Custom multi-agent ecosystem utilizing specialized roles (Architect, SME Writer, Asset Critic, Editorial QA).
- **Communication**: Asynchronous event-driven architecture using `asyncio`.
- **LLM Protocol**: Google Native Gemini API Protocol (`/v1beta/models/...:generateContent`).
  - Native Multimodal `inline_data` support.
  - Native JSON Schema enforcement.
  - **Robust JSON Parsing**: Advanced error-correction for malformed LLM outputs, including unescaped LaTeX backslashes and illegal whitespace characters.
  - VLM-driven semantic candidate selection for local asset matching.
  - **High-Precision Patching**: Fuzzy text matching and indentation-agnostic patching logic via `diff-match-patch`.
  - **Transactional Resilience**: Atomic file operations and breakpoint resume for long-running asset pipelines.
  - "Thinking" token (thoughts) capture and state integration.
  - Intelligent connection pooling and exponential backoff for network resilience.
  - High-concurrency parallel fulfillment with semaphore-based rate limiting.

## Frontend & Tooling
- **Dashboard**: Streamlit (for project monitoring and manual intervention).
- **HTML/CSS Processing**: BeautifulSoup4 and lxml (for semantic manipulation of generated outputs).
- **Visual Auditing**: Playwright (for headless browser-based Visual QA and screenshot capture).

## Documentation & Standards
- **Source Format**: Markdown with custom `:::` container extensions for scripts and visual assets.
- **Target Format**: Industrial-grade, responsive HTML5.