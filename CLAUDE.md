# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

**Magnum Opus HTML Agent** is an enterprise-grade, multi-agent AI system for autonomous production of technical documentation, academic textbooks, and interactive lectures. It uses LangGraph to orchestrate 14+ specialized agents through a stateful workflow with visual verification, structural planning, and a dedicated design system.

### Core Philosophy: ADaPT Framework

- **Logical Rigor**: Content derived from first principles through three-stage planning
- **Visual QA**: Recursive Critic-Fixer loop using Vision-Language Models ensures visual correctness
- **Design Integrity**: Contract-Driven Alignment (CDA) synchronizes JavaScript, CSS, and HTML via shared selector registry
- **Human-in-the-Loop**: Strategic checkpoints for project brief and outline approval

---

## Commands

### Running the System

```bash
# Streamlit GUI (with Human-in-the-Loop checkpoints)
streamlit run app.py

# CLI (headless automated production)
python main.py --input inputs/prompt.txt --output workspaces/workspace/project_name/

# With custom API endpoint
python main.py --input inputs/prompt.txt --api-url http://localhost:3000 --auth-token your_token

# Test API connection
python main.py --test-connection --api-url http://localhost:3000

# Debug mode (saves intermediate states)
python main.py --input inputs/prompt.txt --debug

# Skip Markdown QA phase
python main.py --input inputs/prompt.txt --skip-qa
```

### Development

```bash
# Activate the local micromamba environment
micromamba activate pdf_process

# Install dependencies (if not already installed)
pip install -r requirements.txt

# Install headless browser (required for Visual QA and Image Sourcing)
playwright install chromium

# Run tests
python tests/test_system.py
python tests/test_gemini_client.py
python tests/test_qa_full_cycle.py
```

---

## Architecture

### Three-Phase Workflow

**Phase 1: Strategic Planning**
1. **Clarifier Agent** → Generates 3-5 targeted questions to eliminate ambiguity
2. **Refiner Agent** → Synthesizes user input + answers into Project Brief
3. **Brief Review Gate** → Human approval checkpoint (workflow interrupt)
4. **Architect Agent** → Generates `manifest.json` with section structure and knowledge map
5. **Outline Review Gate** → Human approval checkpoint (workflow interrupt)
6. **TechSpec Agent** → Generates SOTA Description (execution contract for production)

**Phase 2: Content Production**
1. **Writer Agent** (loop) → Generates exhaustive Markdown sections (2000-5000 words each)
2. **Markdown QA Agent** → Internal 3-phase loop: Critic → Advicer → Fixer
   - Can trigger `REWRITE` flag to send content back to Writer
   - Max 3 iterations per cycle
3. **Markdown Review Gate** → Human approval checkpoint (workflow interrupt)
4. **Design Tokens Agent** → Generates single-source-of-truth design spec (`design_tokens.json`)
5. **CSS Generator Agent** → Creates production CSS with `style_mapping.json` contract
6. **JS Generator Agent** → Creates interactive features (TOC, dark mode, progress bar)
7. **Transformer Agent** (loop) → Converts Markdown sections to HTML fragments
8. **Image Sourcing Agent** → VLM-powered web image search and selection
9. **Assembler Agent** → Concatenates HTML fragments into `final.html`

**Phase 3: Visual Verification**
1. **Visual QA Agent** → Dual-agent loop: VLM Critic → Code Fixer
   - Renders HTML in headless browser, captures screenshots
   - Detects layout/rendering bugs, applies surgical patches
   - Can trigger reassembly if fixes require regeneration

### State Management

The workflow is orchestrated by LangGraph using the `AgentState` Pydantic model (`src/core/types.py`):
- **Checkpointing**: Uses `MemorySaver()` for workflow interrupts
- **Interrupt Points**: `review_brief`, `review_outline`, `markdown_review`
- **State Propagation**: Each agent updates state fields for downstream agents
- **Context Chain**: `AgentState.user_context` property provides residual connection of user intent

### Key Data Contracts

All agents follow strict input/output contracts defined in `src/core/types.py`:

- **Manifest**: Structural blueprint with sections, knowledge_map, metadata
- **DesignTokens**: Single source of truth for visual design (colors, typography, spacing, effects)
- **StyleMapping**: Contract between CSS Generator and Transformer (markdown_pattern → css_selector)
- **SectionInfo**: Individual section metadata with ID, title, summary, estimated_words

---

## Agent Architecture Pattern

All agents follow a standard structure in `src/agents/`:

```python
class SomeAgent:
    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()

    def run(self, state: AgentState, **kwargs) -> AgentState:
        # 1. Extract relevant state
        # 2. Build prompt with system_instruction
        # 3. Call client.generate_structured_async() or generate_async()
        # 4. Update state fields
        # 5. Return updated state
```

### Async Support

Writer and Markdown QA agents use async operations:
- `await writer.run(state)` - Supports streaming for long content
- `await markdown_qa.run(state)` - Parallel critic/fixer operations
- Node functions in `src/orchestration/nodes.py` are marked `async` where needed

---

## Critical Implementation Details

### 1. Contract-Driven Alignment (CDA)

The design system ensures JavaScript, CSS, and HTML are perfectly synchronized:

- **CSS Generator** produces `style_mapping.json` with markdown patterns mapped to CSS selectors
- **JS Generator** expects specific IDs to exist: `#theme-toggle`, `#toc-container`, `#progress-bar`
- **Transformer Agent** reads both `main.js` and `style_mapping.json` to ensure HTML elements match expected selectors
- **Assembler Agent** validates contracts before final assembly

### 2. SSE Robust Streaming

The `GeminiClient` (`src/core/gemini_client.py`) supports Server-Sent Events:
- Prevents SSL timeout errors on long-running requests (64k+ tokens)
- Writer and QA agents use streaming by default
- `generate_async()` with `stream=True` parameter
- Response includes `.thoughts` list for think-preview-action patterns

### 3. Visual QA Screenshot Protocol

Visual QA uses viewport-scrolled screenshots with red badge markers:
- Each HTML section rendered in headless browser (DrissionPage)
- Screenshots annotated with "PART X" badges for precise localization
- VLM Critic references PART numbers in issue reports
- Code Fixer receives ONE issue at a time for surgical patching

### 4. Markdown QA Loop Mechanics

Three-phase internal loop with specific verdict types:
- **APPROVE**: Content passes, workflow continues
- **MODIFY**: Triggers Advicer → Fixer, iterates up to 3 times
- **REWRITE**: Sets `rewrite_needed=True`, sends back to Writer

### 5. LangGraph Workflow Execution

The workflow uses `app.astream()` for async node support:
- Interrupts are handled in `run_workflow()` function in `src/orchestration/workflow_html.py`
- User feedback at interrupt points updates state via `app.update_state()`
- Setting `current_state = None` after updates triggers workflow resume
- Debug mode saves every state snapshot to `workspace/{job_id}/debug_logs/`

---

## File Organization

### Workspace Structure

Each workflow run creates a job-specific workspace:

```
workspaces/workspace/{job_id}/
├── md/                    # Markdown sections (sec-1.md, sec-2.md, ...)
├── html/                  # HTML fragments (sec-1.html, sec-2.html, ...)
├── assets/
│   ├── style.css          # Generated CSS from Design Tokens
│   ├── main.js            # Interactive features
│   └── images/            # Sourced images
├── outline.json           # Manifest from Architect Agent
├── design_tokens.json     # Design system specification
├── style_mapping.json     # CSS contract for Transformer
├── final.html             # Assembled complete document
└── debug_logs/            # State snapshots (if --debug enabled)
    ├── step_001.json
    ├── step_002.json
    └── ...
```

### Agent Organization

```
src/agents/
├── clarifier_agent.py      # Question generation
├── refiner_agent.py        # Project Brief synthesis
├── architect_agent.py      # Manifest generation
├── techspec_agent.py       # SOTA Description
├── writer_agent.py         # Markdown content generation (async)
├── markdown_qa_agent.py    # Orchestrates Critic-Advicer-Fixer loop (async)
├── design_tokens_agent.py  # Design system specification
├── css_generator_agent.py  # Production CSS generation
├── js_generator_agent.py   # Interactive features
├── transformer_agent.py    # Markdown to HTML conversion
├── image_sourcing_agent.py # VLM-powered image search
├── assembler_agent.py      # HTML assembly and validation
├── visual_qa_agent.py      # Visual QA orchestration
├── visual_qa/
│   ├── critic.py           # VLM visual inspection
│   └── fixer.py            # Surgical code patching
└── markdown_qa/
    ├── critic.py           # Content quality assessment
    ├── advicer.py          # Action plan generation
    └── fixer.py            # Precise content patching
```

---

## API Client Configuration

The system uses a custom `GeminiClient` that wraps the AIClient-2-API proxy (OpenAI-compatible):

- Default endpoint: `http://localhost:3000`
- Default model: `gemini-3-flash-preview`
- Authentication: Bearer token (env var `GEMINI_AUTH_PASSWORD`)
- Timeout: 120s default (configurable)

### Structured Output

Agents use JSON Schema-constrained generation:

```python
response = await client.generate_structured_async(
    prompt="...",
    system_instruction="...",
    schema={"type": "object", "properties": {...}},
    temperature=0.3  # Lower temp for structured output
)
# response.json_data contains validated JSON
```

---

## Testing Strategy

Tests are organized by feature area in `tests/`:

- `test_system.py` - End-to-end workflow validation
- `test_gemini_client.py` - API client functionality
- `test_qa_*.py` - Markdown QA loop variations (full cycle, stress tests, complex loops)
- `test_parallel_*.py` - Concurrent operations
- `test_image_sourcing_*.py` - Image search and selection

Tests create isolated workspaces in `workspaces/workspace_test/` and `workspaces/workspace_debug/`.

---

## Debugging Workflow Issues

### Enable Debug Mode

```bash
python main.py --input inputs/prompt.txt --debug
```

This saves every state snapshot to `workspace/{job_id}/debug_logs/step_XXX.json`.

### Common Issues

**Agent not receiving user feedback**:
- Check that feedback fields are correctly set in interrupt handlers (`run_workflow()`)
- Verify `app.update_state(config, new_state.model_dump())` is called
- Ensure `current_state = None` after update to trigger resume

**Visual QA not detecting issues**:
- Verify headless browser is installed: `playwright install chromium`
- Check screenshot quality in debug output
- Ensure VLM model supports vision (multimodal)

**Contract-Driven Alignment failures**:
- Verify `style_mapping.json` is generated before Transformer runs
- Check that Transformer reads `main.js` to discover expected IDs
- Validate CSS classes in `style.css` match mapping

**Streaming timeout errors**:
- Ensure `stream=True` is set for long-running agents (Writer, QA)
- Increase timeout in `GeminiClient` initialization
- Check proxy stability with `--test-connection`

---

## Extending the System

### Adding a New Agent

1. Create agent file in `src/agents/new_agent.py`
2. Follow standard pattern: `__init__(client)`, `run(state) -> state`
3. Define state fields in `AgentState` (`src/core/types.py`)
4. Add node function in `NodeFactory` (`src/orchestration/nodes.py`)
5. Wire into workflow graph in `create_workflow()` (`src/orchestration/workflow_html.py`) or `create_sota2_workflow()` (`src/orchestration/workflow_markdown.py`)
6. Add conditional edge logic if needed (`src/orchestration/edges.py`)

### Modifying Agent Behavior

Agents use system instructions + structured output to enforce behavior:
- Modify prompts in agent files
- Adjust JSON schemas for stricter validation
- Lower temperature for more deterministic output
- Add few-shot examples in prompts for complex tasks

### Customizing the Design System

Edit Design Tokens Agent to modify default design decisions:
- Color palettes, typography scales
- Component specifications (cards, callouts, buttons)
- Spacing system, effects (shadows, radii)

The CSS and JS Generators automatically consume the updated tokens.
