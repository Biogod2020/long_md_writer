# Technology Stack

## Core Engine
- **Language**: Python 3.x
- **Orchestration**: LangGraph (for multi-agent state management and complex workflows).
- **Data Validation**: Pydantic (for strictly typed inter-agent communication and configuration).

## Agent Architecture
- **Framework**: Custom multi-agent ecosystem utilizing specialized roles (Architect, SME Writer, Asset Critic, Editorial QA).
- **Communication**: Asynchronous event-driven architecture using `asyncio`.

## Frontend & Tooling
- **Dashboard**: Streamlit (for project monitoring and manual intervention).
- **HTML/CSS Processing**: BeautifulSoup4 and lxml (for semantic manipulation of generated outputs).
- **Visual Auditing**: Playwright (for headless browser-based Visual QA and screenshot capture).

## Documentation & Standards
- **Source Format**: Markdown with custom `:::` container extensions for scripts and visual assets.
- **Target Format**: Industrial-grade, responsive HTML5.