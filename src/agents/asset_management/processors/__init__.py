"""
Asset Management Processors

Modular processors for different asset generation and analysis tasks.
"""

from ...svg_generation.processor import SVG_GENERATION_PROMPT, extract_svg, generate_svg_async
from .mermaid import MERMAID_GENERATION_PROMPT, extract_mermaid, generate_mermaid_async
from .vision import VISION_TAGGING_PROMPT, analyze_image, analyze_image_async
from .focus import FOCUS_CALCULATION_PROMPT, compute_focus, compute_focus_async

__all__ = [
    "SVG_GENERATION_PROMPT",
    "extract_svg",
    "generate_svg_async",
    "MERMAID_GENERATION_PROMPT",
    "extract_mermaid",
    "generate_mermaid_async",
    "VISION_TAGGING_PROMPT",
    "analyze_image",
    "analyze_image_async",
    "FOCUS_CALCULATION_PROMPT",
    "compute_focus",
    "compute_focus_async",
]
