#!/usr/bin/env node

import { constants as fsConstants } from 'node:fs'
import { copyFile, mkdir, readFile, readdir } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import path from 'node:path'
import process from 'node:process'
import readline from 'node:readline/promises'
import { fileURLToPath } from 'node:url'

import { LongWriterHost, loadHostConfig } from './app-server/host.js'
import { loadLocalEnv } from './lib/local-env.js'
import { RunRecorder } from './app-server/run-recorder.js'

loadLocalEnv()

function usage() {
  return `Usage:
  longwriter prepare --run RUN_DIR --config CONFIG_JSON --task TASK_FILE [--input FILE ...] [--image FILE ...]
  longwriter start  --run RUN_DIR --config CONFIG_JSON [--task TASK_FILE] [--input FILE ...] [--non-interactive]
  longwriter resume --run RUN_DIR --config CONFIG_JSON [--instruction-file FILE] [--non-interactive]
  longwriter restart --run RUN_DIR --config CONFIG_JSON [--non-interactive]
  longwriter status --run RUN_DIR

The run directory owns task.txt, run.json, events.jsonl, and workspace/. Provider
credentials are read only from the environment variable named by CONFIG_JSON.`
}

function parseArgs(argv) {
  const [command, ...rest] = argv
  const values = { input: [], image: [] }
  for (let index = 0; index < rest.length; index += 1) {
    const token = rest[index]
    if (token === '--non-interactive') {
      values.nonInteractive = true
      continue
    }
    if (!token.startsWith('--')) throw new Error(`unexpected argument: ${token}`)
    const name = token.slice(2).replaceAll('-', '_')
    const value = rest[index + 1]
    if (value === undefined || value.startsWith('--')) throw new Error(`${token} requires a value`)
    index += 1
    if (name === 'input' || name === 'image') values[name].push(value)
    else values[name] = value
  }
  return { command, values }
}

async function sha256(file) {
  const bytes = await readFile(file)
  return createHash('sha256').update(bytes).digest('hex')
}

async function runtimeFingerprint() {
  const root = path.dirname(fileURLToPath(import.meta.url))
  const excludedDirectories = new Set(['node_modules', '.python-cache', 'test', 'docs', 'examples'])
  const includedExtensions = new Set(['.js', '.json', '.py', '.swift', '.yaml', '.yml'])
  const files = []
  async function walk(directory) {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      if (entry.name.startsWith('.') && entry.name !== '.npmrc') continue
      const absolute = path.join(directory, entry.name)
      if (entry.isDirectory()) {
        if (!excludedDirectories.has(entry.name)) await walk(absolute)
      } else if (entry.isFile() && (includedExtensions.has(path.extname(entry.name)) || entry.name === 'pnpm-lock.yaml')) {
        files.push(absolute)
      }
    }
  }
  await walk(root)
  files.sort()
  const digest = createHash('sha256')
  for (const file of files) {
    digest.update(path.relative(root, file))
    digest.update('\0')
    digest.update(await readFile(file))
    digest.update('\0')
  }
  return { sha256: digest.digest('hex'), file_count: files.length }
}

async function copyInput(source, inputDirectory) {
  const absolute = path.resolve(source)
  const target = path.join(inputDirectory, path.basename(absolute))
  await mkdir(inputDirectory, { recursive: true })
  try {
    await copyFile(absolute, target, fsConstants.COPYFILE_EXCL)
  } catch (error) {
    if (error.code !== 'EEXIST') throw error
    if (await sha256(absolute) !== await sha256(target)) {
      throw new Error(`input basename collision with different content: ${target}`)
    }
  }
  return { source: absolute, path: path.relative(path.dirname(inputDirectory), target), sha256: await sha256(target) }
}

function questionHandler(nonInteractive) {
  if (nonInteractive) {
    return async questions => {
      throw new Error(`non-interactive run requires clarification: ${questions.map(item => item.question).join(' | ')}`)
    }
  }
  return async questions => {
    const terminal = readline.createInterface({ input: process.stdin, output: process.stdout })
    const answers = {}
    try {
      for (const question of questions) {
        process.stdout.write(`\n${question.header}: ${question.question}\n`)
        if (question.options) {
          question.options.forEach((option, index) => {
            process.stdout.write(`  ${index + 1}. ${option.label} — ${option.description}\n`)
          })
        }
        const answer = await terminal.question('> ')
        const numeric = Number.parseInt(answer, 10)
        const resolved = question.options && Number.isSafeInteger(numeric) && question.options[numeric - 1]
          ? question.options[numeric - 1].label
          : answer
        answers[question.id] = { answers: [resolved] }
      }
    } finally {
      terminal.close()
    }
    return { answers }
  }
}

async function prepareRun(values, allowPrepared = false) {
  if (!values.run || !values.config) throw new Error('prepare/start requires --run and --config')
  const runDirectory = path.resolve(values.run)
  const recorder = new RunRecorder(runDirectory)
  try {
    const state = await recorder.load()
    if (allowPrepared && state.status === 'prepared') {
      if (path.resolve(values.config) !== state.config_file) {
        throw new Error(`prepared run requires config ${state.config_file}`)
      }
      return {
        recorder,
        state,
        config: await loadHostConfig(state.config_file),
        task: await readFile(state.task_file, 'utf8'),
      }
    }
    throw new Error(`run.json already exists in ${runDirectory}; use resume or choose a new run directory`)
  } catch (error) {
    if (error.code !== 'ENOENT') throw error
  }
  const workspace = path.join(runDirectory, 'workspace')
  const sourceTaskPath = path.resolve(values.task ?? path.join(runDirectory, 'task.txt'))
  const taskPath = path.join(runDirectory, 'task.txt')
  await mkdir(runDirectory, { recursive: true })
  if (sourceTaskPath !== taskPath) {
    try {
      await copyFile(sourceTaskPath, taskPath, fsConstants.COPYFILE_EXCL)
    } catch (error) {
      if (error.code !== 'EEXIST') throw error
      if (await sha256(sourceTaskPath) !== await sha256(taskPath)) {
        throw new Error(`task.txt already exists with different content in ${runDirectory}`)
      }
    }
  }
  const task = await readFile(taskPath, 'utf8')
  await mkdir(workspace, { recursive: true })
  const inputs = []
  for (const file of values.input) inputs.push(await copyInput(file, path.join(workspace, 'inputs')))
  const images = []
  for (const file of values.image) images.push(await copyInput(file, path.join(workspace, 'inputs')))

  const config = await loadHostConfig(values.config)
  const runtime = await runtimeFingerprint()
  const state = await recorder.create({
    status: 'prepared',
    task_file: taskPath,
    task_sha256: await sha256(taskPath),
    config_file: path.resolve(values.config),
    runtime_source_sha256: runtime.sha256,
    runtime_source_file_count: runtime.file_count,
    workspace,
    inputs,
    images,
    rounds_completed: 0,
  })
  return { recorder, state, config, task }
}

async function prepare(values) {
  const prepared = await prepareRun(values)
  process.stdout.write(`${JSON.stringify(prepared.state, null, 2)}\n`)
}

async function start(values) {
  const { recorder, state, config, task } = await prepareRun(values, true)
  const workspace = state.workspace
  const inputs = state.inputs ?? []
  const images = state.images ?? []
  await recorder.update({ status: 'starting', started_at: new Date().toISOString() })
  const host = new LongWriterHost({
    config,
    workspace,
    recorder,
    answerQuestions: questionHandler(values.nonInteractive),
  })
  try {
    const inputSummary = inputs.length === 0
      ? ''
      : `\n\nAdditional inputs copied under workspace/inputs/:\n${inputs.map(item => `- ${item.path} (sha256 ${item.sha256})`).join('\n')}`
    const imageSummary = images.length === 0
      ? ''
      : `\n\nNative image attachments copied under workspace/inputs/:\n${images.map(item => `- ${item.path} (sha256 ${item.sha256})`).join('\n')}`
    const result = await host.start(
      `${task.trim()}${inputSummary}${imageSummary}`,
      images.map(item => path.join(workspace, item.path)),
    )
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`)
  } finally {
    await host.close()
  }
}

async function resume(values) {
  if (!values.run || !values.config) throw new Error('resume requires --run and --config')
  const recorder = new RunRecorder(values.run)
  const state = await recorder.load()
  if (!state.thread_id) throw new Error('run.json does not contain a resumable thread_id')
  const config = await loadHostConfig(values.config)
  const host = new LongWriterHost({
    config,
    workspace: state.workspace,
    recorder,
    answerQuestions: questionHandler(values.nonInteractive),
  })
  try {
    let operatorInstruction = ''
    if (values.instruction_file) {
      const instructionFile = path.resolve(values.instruction_file)
      operatorInstruction = await readFile(instructionFile, 'utf8')
      if (!operatorInstruction.trim()) throw new Error('resume instruction file must not be empty')
      await recorder.update({
        last_resume_instruction: {
          path: instructionFile,
          sha256: await sha256(instructionFile),
          applied_at: new Date().toISOString(),
        },
      })
    }
    const result = await host.resume(state.thread_id, state.rounds_completed ?? 0, operatorInstruction)
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`)
  } finally {
    await host.close()
  }
}

async function restart(values) {
  if (!values.run || !values.config) throw new Error('restart requires --run and --config')
  const recorder = new RunRecorder(values.run)
  const state = await recorder.load()
  if (!state.thread_id) throw new Error('run.json does not contain a previous thread_id')
  const config = await loadHostConfig(values.config)
  const runtime = await runtimeFingerprint()
  const runtimeHistory = [...(state.runtime_history ?? [])]
  if (state.runtime_source_sha256 && state.runtime_source_sha256 !== runtime.sha256) {
    runtimeHistory.push({
      sha256: state.runtime_source_sha256,
      file_count: state.runtime_source_file_count,
      replaced_at: new Date().toISOString(),
    })
  }
  await recorder.update({
    runtime_source_sha256: runtime.sha256,
    runtime_source_file_count: runtime.file_count,
    runtime_history: runtimeHistory,
  })
  const host = new LongWriterHost({
    config,
    workspace: state.workspace,
    recorder,
    answerQuestions: questionHandler(values.nonInteractive),
  })
  try {
    const result = await host.restart(state.thread_id)
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`)
  } finally {
    await host.close()
  }
}

async function status(values) {
  if (!values.run) throw new Error('status requires --run')
  const recorder = new RunRecorder(values.run)
  process.stdout.write(`${JSON.stringify(await recorder.load(), null, 2)}\n`)
}

async function main() {
  const { command, values } = parseArgs(process.argv.slice(2))
  if (command === 'prepare') return prepare(values)
  if (command === 'start') return start(values)
  if (command === 'resume') return resume(values)
  if (command === 'restart') return restart(values)
  if (command === 'status') return status(values)
  throw new Error(usage())
}

main().catch(error => {
  process.stderr.write(`longwriter: ${error.message}\n`)
  process.exitCode = 1
})
