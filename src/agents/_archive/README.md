# Archived Agents

This directory contains legacy agent implementations that have been superseded by newer, more modular designs.

## Contents

### `design_agent_legacy.py` (Archived: 2026-01-04)

**Original Purpose**: Combined design team agent that handled CSS, JS, and Style Mapping generation in a single agent.

**Reason for Archival**: Replaced by SOTA separation of concerns architecture:
- `DesignTokensAgent` - Generates design tokens as single source of truth
- `CSSGeneratorAgent` - Generates CSS based on design tokens
- `JSGeneratorAgent` - Generates JavaScript independently

**Migration Notes**:
- If you need to restore the old behavior, you can import from this archive
- The new agents are located in:
  - `src/agents/design_tokens_agent.py`
  - `src/agents/css_generator_agent.py`
  - `src/agents/js_generator_agent.py`

## Restoration

To restore an archived agent:
```python
# Instead of:
from ..agents.design_agent import DesignAgent

# Use:
from ..agents._archive.design_agent_legacy import DesignAgent
```
