# DSH adapter architecture

DSH is now an optional runtime adapter, not the LongWriter product boundary.
The current ownership split is documented in [ARCHITECTURE.md](ARCHITECTURE.md).

`adapters/dsh/` owns only:

- DSH Goal creation, resume, and completion;
- mapping DSH tool schemas onto `PublicationKernel`;
- starting a fresh read-only reviewer child Session;
- attesting that the isolated execution actually occurred;
- DSH version probes and profile composition.

`packages/core/` owns canonical state, shared revision, cross-process locking,
deterministic validation, review receipt eligibility, SVG evidence, and
finalization. DSH upgrades must therefore remain contained inside
`adapters/dsh/`.

The old `dsh-native/` directory is retained only as a compatibility install
path and re-exports the adapter.
