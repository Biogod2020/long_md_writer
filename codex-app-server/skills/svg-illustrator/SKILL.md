---
name: svg-illustrator
description: Create or revise self-contained publication SVG figures, bind them to a visual plan, run deterministic geometry checks, inspect retained previews, and record review evidence. Use for diagrams, schemas, flows, charts, and explanatory vector figures; not photos or raster illustration.
---

# SVG Illustrator

Draw the SVG source yourself. This is a drawing and verification workflow, not
an image-generation service: its gates never call a model, repair a draft, or
decide scientific correctness.

## Workflow

1. Define the visual job: reader, relation to show, required labels, exact
   manuscript section, figure type, and final publication width. Record a
   falsifiable scientific claim, checks for complete topology or physical
   conservation, and the intended reading order before drawing.
2. Draw a self-contained SVG with a viewBox and local fragment references only.
   Keep text at 8 pt or larger after scaling to the planned single- or
   double-column width. Use labels to decode relationships, not as paragraph
   containers. Keep at most three functional colour families and pair colour
   with line style, fill, shape, or explicit labels.
3. Use a consistent visual grammar: distinguish data from operations, use
   arrows for signals, put explicit signs on algebraic junctions, and use
   aligned stage containers for separate phases. Keep every required input and
   source-to-sink path visibly connected. Route connectors around text with a
   clear margin; use `data-allow-overlap="true"` only for an intentional,
   visually protected annotation.
4. Run the deterministic source check while iterating. Fix every safety or
   structure error; treat its score as a baseline, never semantic proof.
5. Submit the final candidate with concrete caption and alt text, then run
   geometry preflight on that exact registered SVG. Inspect its retained PNG
   preview for clipped labels, connector collisions, text density, whitespace,
   contrast, semantic completeness, and reading order.
6. Record a pass or fail review tied to that preview. On a failed candidate,
   append a corrected successor rather than overwriting its source or evidence.

## LongMDWriter integration

Inside a LongMDWriter Codex App Server thread, use `plan_visuals`, `svg_check`,
`svg_submit`, `svg_preflight`, then `inspect_visual` with the current asset id
and passing preflight id. The host sends that one retained PNG to an ephemeral
reviewer and returns only its hash-bound text receipt; reference the SVG only
after a passing review. Set
`dry_run` to true when checking the exact submission without writing. Never
write `assets/manifest.json`, `assets/svg/`, or `assets/reviews/` through a
generic file tool.

Outside the agent thread, use the portable CLI from the bundle:

    node codex-app-server/svg/cli.js check --file figure.svg
    node codex-app-server/svg/cli.js render --file figure.svg --out /tmp/figure.png
    node codex-app-server/svg/cli.js plan --workspace WORKSPACE --contract visual-contract.json
    node codex-app-server/svg/cli.js submit --workspace WORKSPACE --file figure.svg --visual-plan-id figure-1 --used-in section-1 --caption "..." --alt-text "..."
    node codex-app-server/svg/cli.js preflight --workspace WORKSPACE --asset-id figure-1
    node codex-app-server/svg/cli.js review --workspace WORKSPACE --asset-id figure-1 --preflight-id preflight-... --reviewer reviewer-1 --verdict pass --summary "..." --checked-label "Required label"

Submission re-runs the source gate and appends the SVG through the domain store.
Preflight registers its PNG derivative and receipt; `inspect_visual` records the
independent inspection evidence. See `references/longmdwriter.md` for the repository
contract, including revision successors and final-validation rules.

Repository maintainers can render the general, synthetic quality suite with:

    pnpm run benchmark:svg-quality -- --out /tmp/longwriter-svg-quality

## Safety boundary

Do not include script, foreignObject, iframe, object, embed, event-handler
attributes, DOCTYPE or entity declarations, remote URLs, data URLs, or CSS
references outside the SVG. Do not call a figure complete solely because a gate
passes: verify its labels and visual claim against surrounding prose.
