# Track Spec: SOTA Output Refinement (Paths, Rendering & Language)

## Problem
The final `final_full.md` from job `sota2_20260223_220554` has three regressions:
1. **Broken Paths**: Images use relative parent paths instead of the flat `resource/` folder.
2. **Missing Rendering**: Captions aren't parsed as Markdown due to HTML block spacing issues.
3. **Language Inconsistency**: Sourced image captions drifted into English despite Chinese content.

## Goals
1. **Physical Patcher**: Create a one-time script to fix the current output.
2. **Core Logic Update**:
    - Update `AssetEntry.to_img_tag` to support aggressive flat-pathing.
    - Update `generate_figure_html` to inject mandatory blank lines.
    - Update `refine_caption_async` prompt to force language alignment with section context.
