# Specification: Repository Tidy-Up

## 1. Overview
Organize the project root directory to improve readability and professionalism. This involves moving scripts, tests, and documentation to their respective standard directories while preserving all existing functionality and strictly ignoring task-tracking files.

## 2. Functional Requirements
- **Script Relocation**: Move core entry points and utility scripts (e.g., `main.py`, `main_markdown.py`, `app.py`) to the `scripts/` directory.
- **Test Relocation**: Move any root-level test files (e.g., `test_architect.py`) to the `tests/` directory.
- **Documentation & Plan Relocation**: Move roadmap and technical planning documents (e.g., `SOTA_Upgrade_Plan_Detailed.md`, `omnimind_project.md`, `AGENTS.md`) to the `docs/` or `conductor/` directory as appropriate.
- **Cleanup**: Remove ephemeral log files (e.g., `e2e_debug.log`, `nohup.out`) and raw AI artifacts (e.g., `architect_raw_response.txt`) by moving them to `data/logs_and_artifacts/`.
- **Preserved Files (STRICT)**: Do NOT move or modify `TODO.md`, `TODO_CN.md`, `HTODO_CN.md`, `MTODO_CN.md`, `requirements.txt`, `.gitignore`, `CLAUDE.md`, or `GEMINI.md`.

## 3. Acceptance Criteria
- Project root is clean, containing only standard project configuration files and the preserved `TODO` lists.
- Original functions remain intact. (Note: Relocating entry points like `main.py` may require the user to adjust their execution commands).
- No data loss of planning or technical documents.

## 4. Out of Scope
- Consolidating or editing the content of `TODO` files.
- Refactoring internal code logic.
