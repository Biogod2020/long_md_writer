/**
 * SVG -> PNG renderer for an optional local preview.
 *
 * Backend ladder (first available wins):
 *   1. @resvg/resvg-js  — pure WASM/native renderer, no browser, no network
 *   2. cairosvg CLI      — python3 -m cairosvg when installed on the host
 *   3. null              — no renderer: callers can report preview unavailable
 *
 * The result of resolveRenderer() is cached for the process lifetime.
 * @module longwriter/svg-renderer
 */

import { spawn } from 'node:child_process'

let cached

export function resetRendererCache() {
  cached = undefined
}

export async function resolveRenderer() {
  if (cached !== undefined) return cached
  cached = await probeRenderer()
  return cached
}

async function probeRenderer() {
  try {
    const { Resvg } = await import('@resvg/resvg-js')
    if (typeof Resvg !== 'function') throw new Error('resvg-js has no Resvg export')
    return {
      backend: 'resvg-js',
      render: async (svg, { timeoutMs = 15000 } = {}) => {
        const resvg = new Resvg(svg, { fitTo: { mode: 'width', value: 1024 } })
        const rendered = resvg.render()
        if (!rendered || rendered.width === 0 || rendered.height === 0) {
          throw new Error('resvg produced an empty bitmap')
        }
        return new Uint8Array(rendered.asPng())
      },
    }
  } catch {
    // resvg-js is not importable: fall through to the CLI backend
  }

  const cairosvg = await probeCairosvg()
  if (cairosvg) {
    return {
      backend: 'cairosvg',
      render: (svg, { timeoutMs = 15000 } = {}) => renderWithCairosvg(svg, { timeoutMs }),
    }
  }
  return null
}

async function probeCairosvg() {
  return new Promise(resolve => {
    const child = spawn('python3', ['-c', 'import cairosvg; print("ok")'], { stdio: ['ignore', 'pipe', 'ignore'] })
    let out = ''
    const timer = setTimeout(() => {
      child.kill()
      resolve(false)
    }, 10000)
    child.stdout.on('data', chunk => {
      out += String(chunk)
    })
    child.on('error', () => {
      clearTimeout(timer)
      resolve(false)
    })
    child.on('close', code => {
      clearTimeout(timer)
      resolve(code === 0 && out.trim() === 'ok')
    })
  })
}

function renderWithCairosvg(svg, { timeoutMs = 15000 } = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn('python3', ['-m', 'cairosvg', '-', '-o', '-'], { stdio: ['pipe', 'pipe', 'pipe'] })
    const chunks = []
    let stderr = ''
    const timer = setTimeout(() => {
      child.kill()
      reject(new Error('cairosvg render timed out'))
    }, timeoutMs)
    child.stdout.on('data', chunk => chunks.push(chunk))
    child.stderr.on('data', chunk => {
      stderr += String(chunk)
    })
    child.on('error', error => {
      clearTimeout(timer)
      reject(error)
    })
    child.on('close', code => {
      clearTimeout(timer)
      if (code !== 0) {
        reject(new Error(`cairosvg exited ${code}: ${stderr.slice(0, 200)}`))
        return
      }
      const png = Buffer.concat(chunks)
      if (png.length === 0) {
        reject(new Error('cairosvg produced no output'))
        return
      }
      resolve(new Uint8Array(png))
    })
    child.stdin.end(svg)
  })
}

/** Convenience wrapper used by the portable preview path. */
export async function renderSvgToPng(svg, options = {}) {
  const renderer = await resolveRenderer()
  if (!renderer) return null
  return { png: await renderer.render(svg, options), backend: renderer.backend }
}
