# LongWriter contributor rules

- `packages/core` is the product boundary. It must not import DSH, MCP, LLM, or
  conversation-runtime packages.
- All canonical publication mutations must pass through `PublicationKernel` and
  advance the shared revision exactly once.
- CLI, MCP, and harness adapters must remain thin mappings over Core; do not
  duplicate validation or persistence logic there.
- A reviewer model may return findings, but only a trusted runtime adapter may
  attest isolation, tool policy, and execution identity.
- Preserve hash binding, path containment, append-only evidence, optimistic
  concurrency, and deterministic finalization tests.
- `inputs/` and `conductor/` remain protected historical/source material.
