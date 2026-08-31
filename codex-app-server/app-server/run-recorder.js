import { appendFile, mkdir, readFile, rename, writeFile } from 'node:fs/promises'
import path from 'node:path'

async function atomicJson(file, value) {
  const temporary = `${file}.${process.pid}.tmp`
  await writeFile(temporary, `${JSON.stringify(value, null, 2)}\n`, { encoding: 'utf8', flag: 'wx' })
  await rename(temporary, file)
}

async function atomicText(file, value) {
  const temporary = `${file}.${process.pid}.tmp`
  await writeFile(temporary, value, { encoding: 'utf8', flag: 'wx' })
  await rename(temporary, file)
}

function runMarkdown(state) {
  const inputs = [...(state.inputs ?? []), ...(state.images ?? [])]
    .map(item => `- \`${item.path}\` — \`${item.sha256}\``)
    .join('\n') || '- none'
  const instructionMetadata = state.last_resume_instruction
  const instruction = instructionMetadata
    ? `- Last resume instruction: \`${instructionMetadata.path}\` — \`${instructionMetadata.sha256}\``
    : '- Last resume instruction: none'
  return `# LongMDWriter run

- Status: \`${state.status}\`
- Created: \`${state.created_at}\`
- Updated: \`${state.updated_at}\`
- Model: \`${state.model ?? '(not started)'}\`
- Provider: \`${state.model_provider ?? '(not started)'}\`
- Thread: \`${state.thread_id ?? '(not started)'}\`
- Rounds completed: \`${state.rounds_completed ?? 0}\`
- Task: \`${state.task_file}\`
- Config: \`${state.config_file}\`
- Runtime source: \`${state.runtime_source_sha256 ?? '(legacy run)'}\` (${state.runtime_source_file_count ?? '?'} files)
- Workspace: \`${state.workspace}\`
${instruction}

## Inputs

${inputs}

Machine-readable state is in \`run.json\`; the exact App Server stream is in
\`events.jsonl\`. Thread persistence is isolated under \`.codex-home/\` after
the run starts. Canonical publication output lives under \`workspace/\`.
`
}

export class RunRecorder {
  constructor(runDirectory) {
    this.runDirectory = path.resolve(runDirectory)
    this.statePath = path.join(this.runDirectory, 'run.json')
    this.eventsPath = path.join(this.runDirectory, 'events.jsonl')
    this.queue = Promise.resolve()
    this.state = null
  }

  async create(initialState) {
    await mkdir(this.runDirectory, { recursive: true })
    this.state = {
      schema_version: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      ...initialState,
    }
    await atomicJson(this.statePath, this.state)
    await atomicText(path.join(this.runDirectory, 'RUN.md'), runMarkdown(this.state))
    return this.state
  }

  async load() {
    this.state = JSON.parse(await readFile(this.statePath, 'utf8'))
    return this.state
  }

  async update(patch) {
    const operation = async () => {
      if (!this.state) await this.load()
      this.state = { ...this.state, ...patch, updated_at: new Date().toISOString() }
      await atomicJson(this.statePath, this.state)
      await atomicText(path.join(this.runDirectory, 'RUN.md'), runMarkdown(this.state))
      return this.state
    }
    const result = this.queue.then(operation)
    this.queue = result.then(
      () => undefined,
      () => undefined,
    )
    return result
  }

  record(direction, payload) {
    const line = `${JSON.stringify({ at: new Date().toISOString(), direction, payload })}\n`
    this.queue = this.queue.then(() => appendFile(this.eventsPath, line, 'utf8'))
    return this.queue
  }

  async flush() {
    await this.queue
  }
}
