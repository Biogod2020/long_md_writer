# Implementation Plan

- [ ] **Phase 1: Emergency Physical Fix**
    - Run regex replace on `final_full.md` to fix `src` paths.
    - Add blank lines to `<figcaption>` tags in existing files.
- [ ] **Phase 2: VLM Language Alignment**
    - Modify `src/agents/asset_management/processors/audit.py` to add `MATCH THE LANGUAGE OF THE CONTEXT` constraint.
- [ ] **Phase 3: Structural Guardrails**
    - Update `src/agents/asset_management/utils.py` to ensure `generate_figure_html` always outputs render-friendly HTML.
- [ ] **Phase 4: Validation**
    - Verify `final_full.md` in VSCode Preview.
