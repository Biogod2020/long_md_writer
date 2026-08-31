#!/usr/bin/env node

import { mkdtemp, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import process from 'node:process'

import { buildAppServerArgs, loadHostConfig } from '../app-server/host.js'
import { CodexAppServerClient } from '../app-server/json-rpc-client.js'
import { loadLocalEnv } from '../lib/local-env.js'

loadLocalEnv()

const configPath = process.argv[2]
if (!configPath) throw new Error('usage: node scripts/smoke-resume.js CONFIG_JSON')
const config = await loadHostConfig(configPath)
if (config.provider && !process.env[config.provider.env_key]) throw new Error(`missing ${config.provider.env_key}`)

const codexHome = await mkdtemp(path.join(os.tmpdir(), 'longwriter-resume-home-'))
const calls = []

function createClient() {
  const env = { ...process.env, CODEX_HOME: codexHome }
  const client = new CodexAppServerClient({
    binary: config.codex_binary ?? 'codex',
    args: buildAppServerArgs(config, env),
    cwd: process.cwd(),
    env,
  })
  client.on('stderr', chunk => process.stderr.write(chunk))
  client.setServerRequestHandler(async message => {
    if (message.method === 'item/tool/call' && message.params.tool === 'longwriter_resume_smoke') {
      calls.push(message.params.arguments.message)
      return {
        contentItems: [{ type: 'inputText', text: JSON.stringify({ echoed: message.params.arguments.message }) }],
        success: true,
      }
    }
    if (message.method.endsWith('/requestApproval')) return { decision: 'decline' }
    throw new Error(`unexpected server request: ${message.method}`)
  })
  return client
}

async function runTurn(client, threadId, text) {
  let timeout
  let resolveTurn
  let rejectTurn
  const completed = new Promise((resolve, reject) => {
    resolveTurn = resolve
    rejectTurn = reject
    timeout = setTimeout(() => reject(new Error('resume smoke turn timed out after 120 seconds')), 120_000)
  })
  const listener = message => {
    if (message.method === 'turn/completed' && message.params.threadId === threadId) resolveTurn(message.params.turn)
    if (message.method === 'error' && message.params.threadId === threadId) rejectTurn(new Error(message.params.error?.message ?? 'App Server turn error'))
  }
  client.on('notification', listener)
  try {
    await client.request('turn/start', {
      threadId,
      input: [{ type: 'text', text, text_elements: [] }],
      effort: config.reasoning_effort ?? null,
    })
    const turn = await completed
    if (turn.status !== 'completed') throw new Error(`turn ended with ${turn.status}: ${JSON.stringify(turn.error)}`)
    return turn
  } finally {
    clearTimeout(timeout)
    client.off('notification', listener)
  }
}

const toolSpec = {
  type: 'function',
  name: 'longwriter_resume_smoke',
  description: 'Echo a synthetic phase marker to verify dynamic tools survive App Server resume.',
  inputSchema: {
    type: 'object',
    additionalProperties: false,
    properties: { message: { type: 'string' } },
    required: ['message'],
  },
}

let first
let second
try {
  first = createClient()
  await first.start()
  await first.initialize()
  const started = await first.request('thread/start', {
    model: config.model,
    modelProvider: config.model_provider,
    cwd: process.cwd(),
    runtimeWorkspaceRoots: [process.cwd()],
    approvalPolicy: 'never',
    approvalsReviewer: 'auto_review',
    sandbox: 'read-only',
    ephemeral: false,
    historyMode: 'paginated',
    baseInstructions: 'This is a synthetic persistence test. Call the requested tool once and do no other work.',
    dynamicTools: [toolSpec],
    threadSource: 'longwriter-resume-smoke',
  })
  const threadId = started.thread.id
  const objective = 'Verify process-restart recovery of one durable App Server thread, goal, and dynamic tool contract.'
  await first.request('thread/goal/set', { threadId, objective, status: 'active' })
  await runTurn(first, threadId, 'Call longwriter_resume_smoke exactly once with message "PHASE_ONE". Then answer PHASE_ONE only.')
  await first.close()
  first = null

  second = createClient()
  await second.start()
  await second.initialize()
  await second.request('thread/resume', {
    threadId,
    model: config.model,
    modelProvider: config.model_provider,
    cwd: process.cwd(),
    runtimeWorkspaceRoots: [process.cwd()],
    approvalPolicy: 'never',
    approvalsReviewer: 'auto_review',
    sandbox: 'read-only',
    excludeTurns: true,
  })
  const restored = await second.request('thread/goal/get', { threadId })
  if (restored.goal?.objective !== objective || restored.goal?.status !== 'active') {
    throw new Error(`goal did not survive restart: ${JSON.stringify(restored.goal)}`)
  }
  await runTurn(second, threadId, 'Call longwriter_resume_smoke exactly once with message "PHASE_TWO". Then answer PHASE_TWO only.')
  if (JSON.stringify(calls) !== JSON.stringify(['PHASE_ONE', 'PHASE_TWO'])) {
    throw new Error(`dynamic tool calls did not survive resume: ${JSON.stringify(calls)}`)
  }
  process.stdout.write(`${JSON.stringify({ passed: true, thread_resumed: true, goal_restored: true, dynamic_tools_restored: true, calls })}\n`)
} finally {
  await first?.close()
  await second?.close()
  await rm(codexHome, { recursive: true, force: true })
}
