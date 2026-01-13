"""
Mermaid Processor

Handles Mermaid diagram generation and extraction.
"""

import re
from typing import Optional

from ....core.gemini_client import GeminiClient


MERMAID_GENERATION_PROMPT = """You are a Mermaid.js diagram expert. Create a clear, well-structured, and aesthetically pleasing diagram based on the provided description.

## Content Description
{description}

## Design Principles
- **Clarity & Structure**: Organize the diagram logically with clear hierarchies and connections.
- **Appropriate Chart Type**: Choose the most suitable Mermaid chart type for the data (e.g., flowchart, sequence, class, state, gantt, pie, etc.).
- **Concise Labels**: Use brief and descriptive text for nodes, participants, and relationships.
- **Visual Polish**: Use subgraphs, styling classes, or direction (TB, LR) to improve readability where appropriate.

{style_hints}

## Output Format
Return ONLY the Mermaid code block. Do not include any introductory or concluding text.

```mermaid
...
```
"""


def extract_mermaid(text: str) -> Optional[str]:
    """Extract Mermaid code from text"""
    match = re.search(r'```mermaid\s*([\s\S]*?)```', text)
    if match:
        return match.group(1).strip()
    return None


async def generate_mermaid_async(
    client: GeminiClient,
    description: str,
    style_hints: str = ""
) -> Optional[str]:
    """
    Generate a Mermaid diagram asynchronously.

    Args:
        client: Gemini API client
        description: Diagram description
        style_hints: Additional style hints

    Returns:
        Mermaid code or None
    """
    hints_section = f"## Additional Requirements\n{style_hints}" if style_hints else ""
    prompt = MERMAID_GENERATION_PROMPT.format(
        description=description,
        style_hints=hints_section
    )

    try:
        response = await client.generate_async(
            prompt=prompt,
            system_instruction="You are a Mermaid.js diagram expert. Generate clear and well-structured diagram code.",
            temperature=0.5
        )

        if not response.success:
            print(f"[Mermaid Processor] API error: {response.error}")
            return None

        return extract_mermaid(response.text)

    except Exception as e:
        print(f"[Mermaid Processor] Generation failed: {e}")
        return None


def generate_mermaid(
    client: GeminiClient,
    description: str,
    style_hints: str = ""
) -> Optional[str]:
    """Generate a Mermaid diagram synchronously"""
    hints_section = f"## Additional Requirements\n{style_hints}" if style_hints else ""
    prompt = MERMAID_GENERATION_PROMPT.format(
        description=description,
        style_hints=hints_section
    )

    try:
        response = client.generate(
            prompt,
            system_instruction="You are a Mermaid.js diagram expert. Generate clear and well-structured diagram code."
        )
        return extract_mermaid(response.text)

    except Exception as e:
        print(f"[Mermaid Processor] Generation failed: {e}")
        return None
