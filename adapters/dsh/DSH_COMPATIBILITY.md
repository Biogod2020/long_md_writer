# DSH compatibility

The adapter is pinned to DSH CLI and `@deepseek-ai/dsh-tools` `0.1.0-rc.6` and
the public seam inspected at source commit
`47f943859bef60e4160492346772ded9b24f765a`. DSH-specific upgrades must remain
inside `adapters/dsh/`; `packages/core` must never import DSH packages.
