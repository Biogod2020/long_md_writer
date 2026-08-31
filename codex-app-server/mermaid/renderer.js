/** Render Mermaid source to standalone SVG through the pinned local mmdc. */

import { spawn } from 'node:child_process'
import { access, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const MERMAID_CLI_VERSION = '11.16.0'
const DEFAULT_TIMEOUT_MS = 45_000
const MAX_STDERR_CHARS = 16_000
const MAX_SVG_BYTES = 1_500_000

const CHROME_CANDIDATES = Object.freeze(
  process.platform === 'darwin'
    ? [
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Chromium.app/Contents/MacOS/Chromium',
      ]
    : process.platform === 'linux'
      ? ['/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser']
      : [],
)

function resolveCliPath() {
  const root = import.meta.resolve('@mermaid-js/mermaid-cli')
  return fileURLToPath(new URL('./cli.js', root))
}

async function isAccessible(file) {
  if (!file) return false
  try {
    await access(file)
    return true
  } catch {
    return false
  }
}

/**
 * Prefer a caller/env override, then an already-installed system browser. If
 * neither exists, Puppeteer falls back to its own pinned browser cache.
 */
export async function resolveChromeExecutable(override = process.env.LONGWRITER_CHROME_BIN) {
  if (override) {
    if (await isAccessible(override)) return override
    throw new Error(`Chrome executable is not accessible: ${override}`)
  }
  for (const candidate of CHROME_CANDIDATES) {
    if (await isAccessible(candidate)) return candidate
  }
  return undefined
}

function runProcess(command, args, { signal, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason instanceof Error ? signal.reason : new Error('mermaid render aborted'))
      return
    }
    const child = spawn(command, args, { stdio: ['ignore', 'ignore', 'pipe'] })
    let stderr = ''
    let settled = false
    const settle = (error) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      signal?.removeEventListener('abort', abort)
      if (error) reject(error)
      else resolve()
    }
    const abort = () => {
      child.kill('SIGTERM')
      settle(signal?.reason instanceof Error ? signal.reason : new Error('mermaid render aborted'))
    }
    const timer = setTimeout(() => {
      child.kill('SIGTERM')
      settle(new Error(`mermaid render timed out after ${timeoutMs}ms`))
    }, timeoutMs)
    signal?.addEventListener('abort', abort, { once: true })
    child.stderr.on('data', chunk => {
      if (stderr.length < MAX_STDERR_CHARS) stderr += String(chunk).slice(0, MAX_STDERR_CHARS - stderr.length)
    })
    child.on('error', settle)
    child.on('close', code => {
      if (code === 0) settle()
      else settle(new Error(`mermaid-cli exited ${code}: ${stderr.trim().slice(0, MAX_STDERR_CHARS)}`))
    })
  })
}

/**
 * The injected runner is used only by deterministic tests. Production resolves
 * the package-local CLI and never searches PATH or downloads a renderer.
 */
export async function renderMermaidToSvg(source, options = {}) {
  if (typeof source !== 'string' || source.trim().length === 0) {
    throw new TypeError('mermaid source must be a non-empty string')
  }
  const root = await mkdtemp(path.join(tmpdir(), 'longwriter-mermaid-'))
  const input = path.join(root, 'diagram.mmd')
  const output = path.join(root, 'diagram.svg')
  const config = path.join(root, 'mermaid.json')
  const puppeteer = path.join(root, 'puppeteer.json')
  try {
    const cliPath = options.cliPath ?? resolveCliPath()
    await access(cliPath)
    const executablePath = await resolveChromeExecutable(options.chromePath)
    await Promise.all([
      writeFile(input, source, 'utf8'),
      writeFile(config, `${JSON.stringify({
        securityLevel: 'strict',
        htmlLabels: false,
        flowchart: { htmlLabels: false },
        theme: 'neutral',
        fontFamily: 'Arial, Helvetica, sans-serif',
      })}\n`, 'utf8'),
      writeFile(puppeteer, `${JSON.stringify({
        headless: executablePath ? true : 'shell',
        ...(executablePath ? { executablePath } : {}),
      })}\n`, 'utf8'),
    ])
    const args = [
      cliPath,
      '--input', input,
      '--output', output,
      '--outputFormat', 'svg',
      '--backgroundColor', 'white',
      '--configFile', config,
      '--puppeteerConfigFile', puppeteer,
      '--quiet',
    ]
    await (options.runProcess ?? runProcess)(process.execPath, args, {
      signal: options.signal,
      timeoutMs: options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
    })
    const bytes = await readFile(output)
    if (bytes.byteLength === 0) throw new Error('mermaid-cli produced an empty SVG')
    if (bytes.byteLength > MAX_SVG_BYTES) throw new Error(`mermaid SVG exceeds ${MAX_SVG_BYTES} bytes`)
    const svg = bytes.toString('utf8')
    if (!/<svg\b/iu.test(svg)) throw new Error('mermaid-cli output is not SVG')
    return { svg, backend: `mermaid-cli@${MERMAID_CLI_VERSION}` }
  } finally {
    await rm(root, { recursive: true, force: true })
  }
}
