"""
Editorial QA Module (SOTA 2.0)
Full-context global quality gate components.
"""

from .critic import run_editorial_critic
from .advicer import run_editorial_advicer
from ..markdown_qa.fixer import run_markdown_fixer, apply_patches

__all__ = [
    "run_editorial_critic",
    "run_editorial_advicer",
    "run_markdown_fixer",
    "apply_patches"
]
