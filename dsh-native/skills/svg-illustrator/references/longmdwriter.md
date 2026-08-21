# LongMDWriter SVG contract

Read this reference when working inside a LongMDWriter publication workspace.

## Canonical records

Do not add a visual-planning file. Put plans in `project.json`:

```json
{
  "visual_contract": {
    "schema_version": 1,
    "figures": [{
      "id": "figure-1",
      "section_id": "methods",
      "kind": "diagram",
      "purpose": "Explain the selection flow.",
      "required_labels": ["Input", "Output"],
      "review_required": true
    }]
  }
}
```

`assets/manifest.json` remains append-only. It records the SVG, its PNG
`svg-preview` derivative, `visual_preflights`, and `visual_reviews`; never edit
these fields directly.

## Required sequence

1. Call `plan_visuals` (or CLI `plan`) before submitting an SVG.
2. Iterate with `svg_check` and submit with `visual_plan_id` plus the planned
   section in `used_in`.
3. Call `svg_preflight` / CLI `preflight`. It measures text with CoreText on
   macOS, checks basic clipping/overlap/contrast/labels, and retains the PNG.
4. Inspect the returned preview. Call `svg_record_review` / CLI `review` with
   a truthful verdict and every visible required label before referencing it.
5. Add the returned `assets/svg/<id>.svg` path only to the planned section.

The final validator independently checks the SVG text labels, plan-to-section
binding, current hashes, a passing CoreText preflight, PNG derivative, and a
passing review. A source score or a preview alone is insufficient.

## Correcting a failed candidate

Assets cannot be overwritten. Submit the corrected SVG with
`supersedes_asset_id` set to the failed candidate's asset id. This creates one
linear revision chain; only its current tip may appear in `article.md`. Leave
the old SVG, preview, and failed preflight receipt intact as historical
evidence.
