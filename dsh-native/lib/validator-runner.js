import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const VALIDATOR = path.join(PACKAGE_ROOT, 'python', 'validate_publication.py')
const OUTPUT_LIMIT = 2 * 1024 * 1024

function pythonExecutable() {
  if (process.env.LONGWRITER_PYTHON) return process.env.LONGWRITER_PYTHON
  return process.platform === 'win32' ? 'python' : 'python3'
}

export function runValidator(workspace, signal, timeoutMs = 120_000) {
  return new Promise((resolve, reject) => {
    const child = spawn(
      pythonExecutable(),
      [VALIDATOR, '--workspace', path.resolve(workspace), '--json'],
      {
        cwd: path.resolve(workspace),
        env: { ...process.env, PYTHONUNBUFFERED: '1' },
        stdio: ['ignore', 'pipe', 'pipe'],
        signal,
      },
    )
    let stdout = ''
    let stderr = ''
    let overflow = false
    const timer = setTimeout(() => {
      child.kill('SIGTERM')
    }, timeoutMs)

    const append = (current, chunk) => {
      if (current.length + chunk.length > OUTPUT_LIMIT) {
        overflow = true
        return current
      }
      return current + chunk
    }
    child.stdout.setEncoding('utf8')
    child.stderr.setEncoding('utf8')
    child.stdout.on('data', chunk => { stdout = append(stdout, chunk) })
    child.stderr.on('data', chunk => { stderr = append(stderr, chunk) })
    child.on('error', error => {
      clearTimeout(timer)
      reject(error)
    })
    child.on('close', code => {
      clearTimeout(timer)
      if (overflow) {
        reject(new Error('publication validator output exceeded 2 MiB'))
        return
      }
      let payload
      try {
        payload = JSON.parse(stdout)
      } catch (error) {
        reject(new Error(`publication validator returned invalid JSON: ${error.message}; stderr=${stderr.slice(0, 2000)}`))
        return
      }
      if (code !== 0 && payload?.passed !== false) {
        reject(new Error(`publication validator failed with exit code ${code}: ${stderr.slice(0, 2000)}`))
        return
      }
      resolve(payload)
    })
  })
}
