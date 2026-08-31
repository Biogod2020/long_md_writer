#!/usr/bin/env node

import process from 'node:process'
import { mkdtemp, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'

import { buildAppServerArgs, loadHostConfig } from '../app-server/host.js'
import { CodexAppServerClient } from '../app-server/json-rpc-client.js'
import { loadLocalEnv } from '../lib/local-env.js'

loadLocalEnv()

const configPath = process.argv[2]
if (!configPath) throw new Error('usage: node scripts/smoke-provider.js CONFIG_JSON')
const config = await loadHostConfig(configPath)
if (config.provider && !process.env[config.provider.env_key]) {
  throw new Error(`missing ${config.provider.env_key}`)
}

const codexHome = await mkdtemp(path.join(os.tmpdir(), 'longwriter-codex-home-'))
const client = new CodexAppServerClient({
  binary: config.codex_binary ?? 'codex',
  args: buildAppServerArgs(config),
  cwd: process.cwd(),
  env: { ...process.env, CODEX_HOME: codexHome },
})
let toolCalled = false
let completedTurn
let resolveTurn
const turnDone = new Promise(resolve => { resolveTurn = resolve })

client.on('stderr', chunk => process.stderr.write(chunk))
client.on('notification', message => {
  if (message.method === 'error' || message.method === 'warning' || message.method === 'model/verification') {
    process.stderr.write(`${JSON.stringify(message)}\n`)
  }
  if (message.method === 'turn/completed') {
    completedTurn = message.params.turn
    resolveTurn(completedTurn)
  }
})
client.setServerRequestHandler(async message => {
  if (message.method === 'item/tool/call' && message.params.tool === 'longwriter_provider_smoke') {
    toolCalled = true
    return {
      contentItems: [{ type: 'inputText', text: JSON.stringify({ echoed: message.params.arguments.message, transport: 'dynamic-tool' }) }],
      success: true,
    }
  }
  if (message.method.endsWith('/requestApproval')) return { decision: 'decline' }
  throw new Error(`unexpected server request: ${message.method}`)
})

try {
  await client.start()
  await client.initialize()
  const started = await client.request('thread/start', {
    model: config.model,
    modelProvider: config.model_provider,
    cwd: process.cwd(),
    runtimeWorkspaceRoots: [process.cwd()],
    approvalPolicy: 'never',
    approvalsReviewer: 'auto_review',
    sandbox: 'read-only',
    ephemeral: true,
    historyMode: 'paginated',
    baseInstructions: 'This is a provider transport smoke test. Follow the user instruction exactly and do no other work.',
    dynamicTools: [{
      type: 'function',
      name: 'longwriter_provider_smoke',
      description: 'Echo one synthetic string to verify App Server dynamic tool transport.',
      inputSchema: {
        type: 'object',
        additionalProperties: false,
        properties: { message: { type: 'string' } },
        required: ['message'],
      },
    }],
    threadSource: 'longwriter-provider-smoke',
  })
  await client.request('turn/start', {
    threadId: started.thread.id,
    input: [{
      type: 'text',
      text: 'Call longwriter_provider_smoke exactly once with message "IWORLD_CODEX_OK". Then answer with the echoed value only.',
      text_elements: [],
    }],
    effort: config.reasoning_effort ?? null,
  })
  let timeout
  const turn = await Promise.race([
    turnDone,
    new Promise((_, reject) => {
      timeout = setTimeout(() => reject(new Error('provider smoke timed out after 120 seconds')), 120_000)
    }),
  ])
  clearTimeout(timeout)
  const messages = turn.items.filter(item => item.type === 'agentMessage')
  const answer = messages.at(-1)?.text ?? ''
  if (turn.status !== 'completed' || !toolCalled || !answer.includes('IWORLD_CODEX_OK')) {
    throw new Error(`provider smoke failed: status=${turn.status} toolCalled=${toolCalled} error=${JSON.stringify(turn.error)} answer=${answer.slice(0, 300)}`)
  }
  process.stdout.write(`${JSON.stringify({ passed: true, model: config.model, provider: config.model_provider, tool_called: toolCalled, answer })}\n`)
} finally {
  await client.close()
  await rm(codexHome, { recursive: true, force: true })
}
