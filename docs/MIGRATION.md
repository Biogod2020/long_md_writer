# Migration from the DSH-native layout

Existing workspaces remain valid. On first Core access, a workspace containing
`project.json`, `article.md`, and `assets/manifest.json` is adopted at revision
0 without changing those files. New controlled mutations then create and update
`.longwriter/` runtime metadata.

The old `dsh-native/` path remains a thin compatibility entrypoint. New code
lives in `packages/core`, `packages/cli`, `packages/mcp`, `skills/longwriter`,
and `adapters/dsh`.

Direct edits to canonical files after adoption are rejected because they bypass
revision and review invalidation. Apply edits through CLI, MCP, or a supported
adapter.
