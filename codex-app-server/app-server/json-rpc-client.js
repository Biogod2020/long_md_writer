import { spawn } from 'node:child_process'
import { EventEmitter } from 'node:events'

function protocolError(message, payload) {
  const error = new Error(message)
  error.payload = payload
  return error
}

/** Minimal line-delimited JSON-RPC client for `codex app-server --stdio`. */
export class CodexAppServerClient extends EventEmitter {
  constructor(options = {}) {
    super()
    this.binary = options.binary ?? 'codex'
    this.args = options.args ?? ['app-server', '--stdio']
    this.cwd = options.cwd ?? process.cwd()
    this.env = options.env ?? process.env
    this.child = null
    this.buffer = ''
    this.nextId = 1
    this.pending = new Map()
    this.serverRequestHandler = null
    this.closed = false
  }

  async start() {
    if (this.child) return
    this.child = spawn(this.binary, this.args, {
      cwd: this.cwd,
      env: this.env,
      stdio: ['pipe', 'pipe', 'pipe'],
    })
    this.child.stdout.setEncoding('utf8')
    this.child.stderr.setEncoding('utf8')
    this.child.stdout.on('data', chunk => this.#consume(chunk))
    this.child.stderr.on('data', chunk => this.emit('stderr', chunk))
    this.child.on('error', error => this.#failAll(error))
    this.child.on('close', (code, signal) => {
      this.closed = true
      this.#failAll(protocolError(`codex app-server exited (code=${code}, signal=${signal})`, { code, signal }))
      this.emit('close', { code, signal })
    })
  }

  async initialize() {
    const result = await this.request('initialize', {
      clientInfo: {
        name: 'longwriter',
        title: 'LongMDWriter',
        version: '0.2.0',
      },
      capabilities: {
        experimentalApi: true,
        requestAttestation: false,
      },
    })
    this.notify('initialized')
    return result
  }

  setServerRequestHandler(handler) {
    this.serverRequestHandler = handler
  }

  request(method, params) {
    if (!this.child || this.closed) throw new Error('codex app-server is not running')
    const id = this.nextId++
    const message = { method, id, params }
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, method })
      try {
        this.#send(message)
      } catch (error) {
        this.pending.delete(id)
        reject(error)
      }
    })
  }

  notify(method, params) {
    const message = params === undefined ? { method } : { method, params }
    this.#send(message)
  }

  respond(id, result) {
    this.#send({ id, result })
  }

  respondError(id, code, message, data) {
    this.#send({ id, error: { code, message, ...(data === undefined ? {} : { data }) } })
  }

  async close() {
    if (!this.child || this.closed) return
    const child = this.child
    child.stdin.end()
    await new Promise(resolve => {
      const terminate = setTimeout(() => {
        child.kill('SIGTERM')
      }, 5000)
      const force = setTimeout(() => {
        child.kill('SIGKILL')
      }, 8000)
      const fallback = setTimeout(resolve, 10000)
      child.once('close', () => {
        clearTimeout(terminate)
        clearTimeout(force)
        clearTimeout(fallback)
        resolve()
      })
    })
  }

  #send(message) {
    if (!this.child || this.closed || !this.child.stdin.writable) {
      throw new Error('cannot write to a stopped codex app-server')
    }
    this.emit('send', message)
    this.child.stdin.write(`${JSON.stringify(message)}\n`)
  }

  #consume(chunk) {
    this.buffer += chunk
    while (true) {
      const newline = this.buffer.indexOf('\n')
      if (newline === -1) break
      const line = this.buffer.slice(0, newline).trim()
      this.buffer = this.buffer.slice(newline + 1)
      if (!line) continue
      let message
      try {
        message = JSON.parse(line)
      } catch (error) {
        this.emit('protocolError', protocolError(`invalid JSON from codex app-server: ${error.message}`, line))
        continue
      }
      this.emit('receive', message)
      this.#dispatch(message)
    }
  }

  #dispatch(message) {
    if (Object.hasOwn(message, 'id') && typeof message.method === 'string') {
      void this.#handleServerRequest(message)
      return
    }
    if (Object.hasOwn(message, 'id')) {
      const pending = this.pending.get(message.id)
      if (!pending) {
        this.emit('protocolError', protocolError('response for unknown request id', message))
        return
      }
      this.pending.delete(message.id)
      if (message.error) {
        pending.reject(protocolError(`${pending.method} failed: ${message.error.message ?? 'unknown error'}`, message.error))
      } else {
        pending.resolve(message.result)
      }
      return
    }
    if (typeof message.method === 'string') this.emit('notification', message)
  }

  async #handleServerRequest(message) {
    if (!this.serverRequestHandler) {
      this.respondError(message.id, -32601, `unsupported server request: ${message.method}`)
      return
    }
    try {
      const result = await this.serverRequestHandler(message)
      this.respond(message.id, result)
    } catch (error) {
      this.respondError(message.id, -32000, error.message, { name: error.name })
    }
  }

  #failAll(error) {
    for (const pending of this.pending.values()) pending.reject(error)
    this.pending.clear()
  }
}
