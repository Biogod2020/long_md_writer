---
name: svg-illustrator
description: Create or revise self-contained publication SVG figures, bind them to a visual plan, run deterministic geometry checks, inspect retained previews, and record review evidence. Use for diagrams, schemas, flows, charts, and explanatory vector figures; not photos or raster illustration.
---

# SVG Illustrator

Draw the SVG source yourself. This is a drawing and verification workflow, not
an image-generation service: its gates never call a model, repair a draft, or
decide scientific correctness.

## Workflow

1. Define the visual job: reader, relation to show, required labels, and its
   exact manuscript section. In LongMDWriter, record it before drawing.
2. Draw a self-contained SVG with a viewBox, readable text, a small semantic
   palette, and local fragment references only. Prefer primitives to embedded
   images or foreign content.
3. Run the deterministic source check while iterating. Fix every safety or
   structure error; treat its score as a baseline, never semantic proof.
4. Submit the final candidate with concrete caption and alt text, then run
   geometry preflight on that exact registered SVG. Inspect its retained PNG
   preview for clipped labels, overlaps, contrast, and reading order.
5. Record a pass or fail review tied to that preview. On a failed candidate,
   append a corrected successor rather than overwriting its source or evidence.

## LongMDWriter integration

Inside a DSH publication session, use `plan_visuals`, `svg_check`,
`svg_submit`, `svg_preflight`, inspect `preview_asset_path` with `read_image`,
then `svg_record_review`; reference the SVG only after a passing review. Set
`dry_run` to true when checking the exact submission without writing. Never
write `assets/manifest.json`, `assets/svg/`, or `assets/reviews/` through a
generic file tool.

Outside DSH, use the portable CLI from the bundle:

    node dsh-native/svg/cli.js check --file figure.svg
    node dsh-native/svg/cli.js render --file figure.svg --out /tmp/figure.png
    node dsh-native/svg/cli.js plan --workspace WORKSPACE --contract visual-contract.json
    node dsh-native/svg/cli.js submit --workspace WORKSPACE --file figure.svg --visual-plan-id figure-1 --used-in section-1 --caption "..." --alt-text "..."
    node dsh-native/svg/cli.js preflight --workspace WORKSPACE --asset-id figure-1
    node dsh-native/svg/cli.js review --workspace WORKSPACE --asset-id figure-1 --preflight-id preflight-... --reviewer reviewer-1 --verdict pass --summary "..." --checked-label "Required label"

Submission re-runs the source gate and appends the SVG through the domain store.
Preflight registers its PNG derivative and receipt; review records the final
inspection evidence. See `references/longmdwriter.md` for the repository
contract, including revision successors and final-validation rules.

## Safety boundary

Do not include script, foreignObject, iframe, object, embed, event-handler
attributes, DOCTYPE or entity declarations, remote URLs, data URLs, or CSS
references outside the SVG. Do not call a figure complete solely because a gate
passes: verify its labels and visual claim against surrounding prose.
