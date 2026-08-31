#!/usr/bin/env node

import process from 'node:process'

import { loadHostConfig } from '../app-server/host.js'
import { SearchToolRuntime } from '../app-server/search-tools.js'
import { loadLocalEnv } from '../lib/local-env.js'

loadLocalEnv()

const config = await loadHostConfig(process.argv[2] ?? 'config/iworld-muse12.json')
if (!config.search_bridge) throw new Error('configured search bridge is missing')
const runtime = new SearchToolRuntime({
  command: config.search_bridge.command,
  project: config.search_bridge.project,
  runner: config.search_bridge.runner,
  timeoutMs: config.search_bridge.timeout_ms,
  maxOutputBytes: config.search_bridge.max_output_bytes,
})
const result = await runtime.execute('longwriter_search', {
  query: '12 lead ECG electrode placement',
  count: 3,
  market: 'en-US',
})
if (result.status !== 'ok' || result.returned_count < 1 || result.quality_label === 'poor') {
  throw new Error(`search smoke failed: ${JSON.stringify(result)}`)
}
process.stdout.write(`${JSON.stringify({
  passed: true,
  provider: result.provider,
  returned_count: result.returned_count,
  quality_label: result.quality_label,
  first_url: result.results[0].url,
})}\n`)
