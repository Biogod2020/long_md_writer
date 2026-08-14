# DSH compatibility contract

## Pinned baseline

LongMDWriter pins the verified public preview explicitly:

```text
@deepseek-ai/dsh CLI:   0.1.0-rc.6
@deepseek-ai/dsh-tools: 0.1.0-rc.6
public seam contract inspected at: 47f943859bef60e4160492346772ded9b24f765a
```

The CI workflow installs the exact CLI, installs this bundle into a fresh DSH Web profile, and verifies the composed configuration through `--dump-config`. Do not use caret, tilde, `latest`, or `next` for production deployment. Commit the generated package-manager lockfile in the deployment profile.

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

## Session-format isolation

DSH persistence refuses session logs whose format it cannot faithfully reconstruct and currently provides no general migration chain. This bundle therefore changes the storage namespace whenever the pinned DSH runtime changes:

```text
sessions-longwriter/dsh-0.1.0-rc.6/
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
