# DSH compatibility contract

## Pinned baseline

LongMDWriter pins the verified public preview explicitly:

```text
@deepseek-ai/dsh CLI:   0.1.1-rc.2
@deepseek-ai/dsh-tools: 0.1.1-rc.2
public seam contract inspected at: b150a551b8d465e31e418e1b2eaf5e79bbb7d28e
```

The CI workflow installs the exact CLI, installs this bundle into a fresh DSH Web profile, and verifies the composed configuration through `--dump-config`. Do not use caret, tilde, `latest`, or `next` for production deployment. Commit the generated package-manager lockfile in the deployment profile.

For this standalone bundle's local verification graph, explicit development
dependencies pin the complete DSH peer family to `0.1.1-rc.2`. That prevents a
stale peer auto-install from silently mixing preview generations. The actual
DSH Web host supplies its matching package family from the exact CLI release.

## Public seams consumed

All DSH-dependent behavior is concentrated in `index.js` and `lib/dsh-compat.js`. The bundle imports only the published root export of `@deepseek-ai/dsh-tools`; it never imports an upstream `/src/*` path.

The compatibility adapter probes these public capabilities at mount time:

```text
ctx.tools.register
ctx.tools.guard
ctx.systemPrompt.section
ctx.goals.get/create/resume/complete
ctx.subagents.start
```

Tool execution relies on the public fields:

```text
exec.agent
exec.signal
exec.concludeTurn()
agent.session.header.cwd
```

Reviewer delegation relies on the public one-shot subagent contract:

```text
provider: spawn
request.parent
request.signal
request.outputSchema
request.toolFilter
request.persona
run.result
run.dispose()
```

A missing seam fails plugin activation or the relevant call with a version-specific diagnostic instead of silently degrading.

## Native interaction reused without an adapter

The Web `standard` agent preset already mounts
`@deepseek-ai/dsh-tool-ask-user`, and the Web bundle already mounts the local
attachment store plus image composer UI. LongMDWriter only allows
`ask_user_question` through its execution guard and instructs the root agent to
inspect submitted image blocks. It does not import those packages or call their
services directly, so this is profile composition rather than a new
version-sensitive LongMDWriter seam.

For the pinned release, durable composer attachments are raster images only:
PNG, JPEG, WebP, and GIF. Non-image publication inputs remain ordinary
workspace files under `inputs/`. If a later DSH version adds general file
attachments or LongMDWriter must programmatically import an attachment as a
canonical asset, put that new API use behind `lib/dsh-compat.js` and extend the
real profile contract test before adopting it.

Mermaid rendering is independent of DSH and is pinned separately to
`@mermaid-js/mermaid-cli@11.16.0` and `puppeteer@25.9.0`. It uses the documented
CLI process boundary rather than Mermaid's unstable programmatic Node API.

## Session-format isolation

DSH persistence refuses session logs whose format it cannot faithfully reconstruct and currently provides no general migration chain. This bundle therefore changes the storage namespace whenever the pinned DSH runtime changes:

```text
sessions-longwriter/dsh-0.1.1-rc.2/
sessions-longwriter/dsh-<next-runtime-version>/
```

Never point a new DSH release at the previous directory during an upgrade test.

The only cross-version publication source of truth is:

```text
project.json
article.md
assets/manifest.json
```

When a later DSH release cannot resume an old Session, create a new Session in the new namespace, open the same workspace, and instruct the agent to continue from these files. Do not build a custom session-log migrator unless the upstream project publishes a stable migration contract.

## Upgrade procedure

1. Keep the current production CLI and package pins operational.
2. Record the candidate CLI version, every directly imported package version, and the source contract reviewed for the candidate.
3. Create a new session namespace for the candidate runtime.
4. Update package versions only on an upgrade branch.
5. Run syntax, domain-store, validator, public-import, and real profile-composition tests.
6. Run a live compatibility scenario:
   - initialize a publication;
   - commit at least three chunks;
   - force context compaction;
   - run a fresh reviewer;
   - terminate the process during an active turn;
   - reopen and call `resume_publication`;
   - finalize successfully.
7. Confirm generic write/edit cannot mutate canonical files.
8. Promote the new pins manually. Never auto-update the production profile.

The CI workflow contains a nonblocking `next`-tag probe for early warning, but its result must never change the production pin automatically. The npm `latest` tag is not used for preview tracking because it may lag the `next` compatibility line.
