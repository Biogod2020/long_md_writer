# Spec: Multimodal Intent-Layered Asset Management

## Overview
Implement a visual-aware asset management system that categorizes assets by user intent (Mandatory vs. Suggested). This track ensures that "Mandatory" assets are visible to the AI throughout the entire lifecycle—from planning (Architect) to writing (Writer)—enforcing their usage through multimodal prompts and automated QA.

## Core Requirements

### 1. Intent-Layered Discovery (Phase 0)
- **Categorization**: Support subdirectories `inputs/mandatory/` and `inputs/suggested/`.
- **Visual Foundation**: Upgrade `AssetEntry` to store Base64 image data for immediate multimodal injection without relying on local file paths.
- **Priority Metadata**: Add a `priority` field (`MANDATORY`, `SUGGESTED`, `AUTONOMOUS`) to the UAR registry.

### 2. Visual-Aware Planning (Phase 1)
- **Multimodal Architecting**: The `ArchitectAgent` must receive the actual images and descriptions of all `MANDATORY` assets in its input.
- **Hard Pinning**: The Architect must assign specific `MANDATORY` assets to sections in the `manifest.json` via a new `assigned_assets` field in section metadata.

### 3. Multimodal Writing Protocol (Phase 3)
- **Contextual Injection**: The `WriterAgent` receives the Base64 data of only the assets assigned to the current chapter.
- **Visual Adherence**: The Writer is instructed to "read" the visual details of the image and write specific explanatory text that aligns with the visual evidence.

### 4. Enforcement & QA (Phase 4)
- **Mandatory Coverage Audit**: `EditorialQA` must verify that every asset in the `MANDATORY` pool is correctly referenced in the generated Markdown.
- **Failure Loop**: Missing mandatory assets trigger a `FAIL` verdict and a targeted rewrite.

## Technical Architecture
- **Multimodal Message Format**: Standardize on `[{"text": "..."}, {"inline_data": {"mime_type": "image/png", "data": "base64"}}]`.
- **Additive Injection**: When adding image inputs to `ArchitectAgent` and `WriterAgent`, all existing textual inputs (User Intent, Project Brief, Reference Materials, etc.) MUST be preserved intact. Image data is an augmentation of the context, not a replacement.
- **UAR Persistence**: Base64 data will be stored in `assets.json` for session-long availability.

## Success Criteria
- [ ] `AssetIndexer` correctly identifies assets in the `mandatory` folder.
- [ ] `ArchitectAgent` explicitly assigns a mandatory heart diagram to "Chapter 1" in the manifest.
- [ ] `WriterAgent` references specific visual details found in the provided mandatory image.
- [ ] `EditorialQA` fails a draft if a mandatory logo was not included in the text.
