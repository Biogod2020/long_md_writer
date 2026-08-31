import { spawn } from 'node:child_process'

function schema(properties, required) {
  return {
    type: 'object',
    additionalProperties: false,
    properties,
    required,
  }
}

const TOOL_SPECS = [
  {
    type: 'function',
    name: 'longwriter_search',
    description: 'Search the public web through the repository dsh-bing-search service. Inspect quality_label and open selected sources before relying on snippets.',
    inputSchema: schema({
      query: { type: 'string' },
      count: { type: 'integer', minimum: 1, maximum: 20 },
      offset: { type: 'integer', minimum: 0, maximum: 100 },
      market: { type: 'string' },
      safe_search: { type: 'string', enum: ['Strict', 'Moderate', 'Off'] },
    }, ['query']),
  },
  {
    type: 'function',
    name: 'longwriter_search_images',
    description: 'Search Bing Images or Wikimedia Commons through dsh-bing-search and return ranked image candidates with source pages and relevance signals.',
    inputSchema: schema({
      query: { type: 'string' },
      count: { type: 'integer', minimum: 1, maximum: 20 },
      market: { type: 'string' },
      provider: { type: 'string', enum: ['auto', 'bing_images', 'commons'] },
    }, ['query']),
  },
  {
    type: 'function',
    name: 'longwriter_open',
    description: 'Fetch one public HTTP(S) page through dsh-bing-search and return cleaned readable text.',
    inputSchema: schema({
      url: { type: 'string' },
      max_chars: { type: 'integer', minimum: 1, maximum: 100000 },
    }, ['url']),
  },
  {
    type: 'function',
    name: 'longwriter_find',
    description: 'Find a literal phrase in one public page and return compact surrounding context.',
    inputSchema: schema({
      url: { type: 'string' },
      pattern: { type: 'string' },
      max_matches: { type: 'integer', minimum: 1, maximum: 20 },
      context_chars: { type: 'integer', minimum: 1, maximum: 4000 },
    }, ['url', 'pattern']),
  },
]

export class SearchToolRuntime {
  constructor(options) {
    this.command = options.command ?? 'uv'
    this.project = options.project
    this.runner = options.runner
    this.timeoutMs = options.timeoutMs ?? 60000
    this.maxOutputBytes = options.maxOutputBytes ?? 2_000_000
    if (!this.project || !this.runner) throw new Error('search bridge requires project and runner paths')
  }

  specs() {
    return TOOL_SPECS.map(spec => structuredClone(spec))
  }

  has(tool) {
    return TOOL_SPECS.some(spec => spec.name === tool)
  }

  execute(tool, args, signal) {
    if (!this.has(tool)) throw new Error(`unknown search tool: ${tool}`)
    const operation = {
      longwriter_search: 'search',
      longwriter_search_images: 'search_images',
      longwriter_open: 'open',
      longwriter_find: 'find',
    }[tool]
    return new Promise((resolve, reject) => {
      const child = spawn(this.command, [
        'run', '--frozen', '--project', this.project,
        'python', this.runner, operation,
      ], {
        stdio: ['pipe', 'pipe', 'pipe'],
      })
      let stdout = ''
      let stderr = ''
      let settled = false
      const finish = (fn, value) => {
        if (settled) return
        settled = true
        clearTimeout(timeout)
        signal?.removeEventListener('abort', abort)
        fn(value)
      }
      const abort = () => {
        child.kill('SIGTERM')
        finish(reject, new Error('search call aborted'))
      }
      const timeout = setTimeout(() => {
        child.kill('SIGTERM')
        finish(reject, new Error(`search call timed out after ${this.timeoutMs}ms`))
      }, this.timeoutMs)
      signal?.addEventListener('abort', abort, { once: true })
      child.on('error', error => finish(reject, error))
      child.stdout.setEncoding('utf8')
      child.stderr.setEncoding('utf8')
      child.stdout.on('data', chunk => {
        stdout += chunk
        if (Buffer.byteLength(stdout) > this.maxOutputBytes) {
          child.kill('SIGTERM')
          finish(reject, new Error('search response exceeded output limit'))
        }
      })
      child.stderr.on('data', chunk => {
        stderr += chunk
        if (Buffer.byteLength(stderr) > 65536) stderr = stderr.slice(-65536)
      })
      child.on('close', code => {
        if (settled) return
        if (code !== 0) {
          finish(reject, new Error(`search bridge exited ${code}: ${stderr.trim() || '(no stderr)'}`))
          return
        }
        try {
          finish(resolve, JSON.parse(stdout))
        } catch (error) {
          finish(reject, new Error(`search bridge returned invalid JSON: ${error.message}`))
        }
      })
      child.stdin.end(JSON.stringify(args ?? {}))
    })
  }
}
