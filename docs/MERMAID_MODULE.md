# Mermaid module

## Purpose

The Mermaid lane is the shortest controlled path for structured publication
diagrams. The model supplies ordinary Mermaid text; LongMDWriter validates it,
renders it locally, retains the editable source, and sends the resulting SVG
through the existing visual evidence workflow. It does not call an image model
and does not add a second review system.

```text
plan_visuals
  -> mermaid_submit(dry_run=true)       optional exact render/gate check
  -> mermaid_submit                     retain source + register SVG derivative
  -> svg_preflight                      CoreText geometry + retained PNG
  -> inspect_visual                     one-image ephemeral independent review
  -> reference returned SVG in article.md
```

## Module boundary

- `mermaid/core.js` bounds source size and supported declarations and rejects
  init directives, click actions, active HTML, external URLs, and control
  characters before a browser starts.
- `mermaid/renderer.js` invokes the package-local
  `@mermaid-js/mermaid-cli@11.16.0` with strict Mermaid configuration. It uses
  `LONGWRITER_CHROME_BIN` when set, otherwise an installed system Chrome or
  Chromium, otherwise Puppeteer's pinned browser cache.
- `mermaid/submit.js` resolves the visual plan, performs the exact SVG gate,
  retains `assets/mermaid/mermaid-src-<hash>.mmd`, and registers
  `assets/svg/<id>.svg` with a `derivative_of` record bound to the source asset
  id and SHA-256.
- `mermaid/index.js` exposes only `mermaid_submit` to the App Server dynamic
  domain-tool runtime.

The rendered SVG then uses the existing `svg_preflight` and `inspect_visual`
tools. SVG safety, geometry evidence, visual-plan binding,
revision-chain rules, and final validation are not duplicated or weakened.

## Tool contract

Required inputs are complete Mermaid source, caption, alt text,
`visual_plan_id`, and `used_in`. `used_in` must include the section named by
the visual plan. An optional safe `id` controls the SVG filename. A replacement
for an existing planned figure must provide `supersedes_asset_id`.

`dry_run=true` performs the same local render and SVG gate but writes no source,
asset, or manifest entry. A normal successful call returns both the retained
source path and the registered SVG path. Identical Mermaid source reuses its
content-addressed source asset; the SVG itself remains subject to the existing
append-only revision rules.

Failures are explicit and non-mutating:

- `rejected`: Mermaid or rendered SVG failed a deterministic gate;
- `render_error`: the pinned renderer or browser failed;
- `error`: visual-plan, asset-store, or append-only constraints failed.

An output is not ready for manuscript use merely because it rendered. It must
also pass `svg_preflight`, visible preview inspection, and
`inspect_visual`.

## Maintenance rule

Keep Mermaid policy renderer-independent and test it without a browser. Pin
the CLI and Puppeteer exactly. Upgrade them deliberately, then run the unit
suite plus one real render through the SVG gate. Do not use Mermaid's unstable
programmatic Node API; the module invokes the documented CLI boundary.
