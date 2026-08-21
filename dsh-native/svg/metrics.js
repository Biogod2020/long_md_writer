/**
 * Local text-metric bridge for SVG geometry checks.
 *
 * On macOS it asks CoreText for the same basic glyph metrics the local system
 * uses to render a font. Other hosts retain a deterministic conservative
 * approximation, reported explicitly as such rather than being presented as
 * a true layout measurement.
 *
 * @module longwriter/svg-metrics
 */

import { spawn } from 'node:child_process'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HELPER = fileURLToPath(new URL('./coretext-metrics.swift', import.meta.url))
const MODULE_CACHE = path.join(tmpdir(), 'longwriter-swift-module-cache')

function finiteNumber(value, fallback) {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function normalizeRuns(runs) {
  if (!Array.isArray(runs)) throw new TypeError('text metric runs must be an array')
  return runs.map((run, index) => {
    if (run === null || typeof run !== 'object' || Array.isArray(run)) {
      throw new TypeError(`text metric run ${index} must be an object`)
    }
    if (typeof run.text !== 'string') throw new TypeError(`text metric run ${index}.text must be a string`)
    const fontSize = finiteNumber(run.font_size, NaN)
    if (!(fontSize > 0 && fontSize <= 1_000)) {
      throw new TypeError(`text metric run ${index}.font_size must be a finite number in (0, 1000]`)
    }
    return {
      text: run.text,
      font_size: fontSize,
      ...(typeof run.font_family === 'string' && run.font_family.trim() ? { font_family: run.font_family.trim() } : {}),
    }
  })
}

function approximateOne(run) {
  let width = 0
  for (const character of run.text) {
    if (/\s/u.test(character)) width += 0.33
    else if (/[^\u0000-\u024F]/u.test(character)) width += 1
    else if (/[A-Z0-9]/.test(character)) width += 0.65
    else width += 0.56
  }
  return {
    width: width * run.font_size,
    ascent: run.font_size * 0.78,
    descent: run.font_size * 0.22,
  }
}

export function approximateTextMetrics(runs) {
  return normalizeRuns(runs).map(approximateOne)
}

function validateMeasurements(value, expectedLength) {
  if (!Array.isArray(value) || value.length !== expectedLength) {
    throw new Error('CoreText returned an unexpected measurement count')
  }
  return value.map((metric, index) => {
    if (metric === null || typeof metric !== 'object') {
      throw new Error(`CoreText returned an invalid measurement at index ${index}`)
    }
    const width = finiteNumber(metric.width, NaN)
    const ascent = finiteNumber(metric.ascent, NaN)
    const descent = finiteNumber(metric.descent, NaN)
    if (!(width >= 0 && ascent >= 0 && descent >= 0)) {
      throw new Error(`CoreText returned non-finite metrics at index ${index}`)
    }
    return { width, ascent, descent }
  })
}

export function runCoreTextMetrics(runs, { command = 'swift', timeoutMs = 20_000 } = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, [HELPER], {
      stdio: ['pipe', 'pipe', 'pipe'],
      // Swift normally reaches into a user-global compiler cache. Keep its
      // ephemeral module products under the operating-system temp directory
      // so a sandbox cannot force an unnecessary approximate-metrics fallback.
      env: {
        ...process.env,
        CLANG_MODULE_CACHE_PATH: MODULE_CACHE,
        SWIFT_MODULE_CACHE_PATH: MODULE_CACHE,
      },
    })
    const output = []
    let stderr = ''
    let settled = false
    const finish = callback => value => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      callback(value)
    }
    const succeed = finish(resolve)
    const fail = finish(reject)
    const timer = setTimeout(() => {
      child.kill()
      fail(new Error('CoreText metric helper timed out'))
    }, timeoutMs)
    child.stdout.on('data', chunk => output.push(chunk))
    child.stderr.on('data', chunk => { stderr += String(chunk) })
    child.on('error', error => fail(error))
    child.on('close', code => {
      if (code !== 0) {
        fail(new Error(`CoreText metric helper exited ${code}: ${stderr.trim().slice(0, 300)}`))
        return
      }
      try {
        const parsed = JSON.parse(Buffer.concat(output).toString('utf8'))
        succeed(parsed)
      } catch (error) {
        fail(error)
      }
    })
    child.stdin.end(JSON.stringify(runs))
  })
}

/**
 * Measure text runs with CoreText where available. Supplying `runner` is an
 * intentional test seam; the production default remains local CoreText only.
 */
export async function measureTextRuns(runs, options = {}) {
  const normalized = normalizeRuns(runs)
  const runner = options.runner ?? runCoreTextMetrics
  const useCoreText = options.forceCoreText === true || (options.platform ?? process.platform) === 'darwin'
  if (useCoreText) {
    try {
      const measured = await runner(normalized, options)
      return {
        metric_mode: 'coretext',
        measurements: validateMeasurements(measured, normalized.length),
        warnings: [],
      }
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error)
      return {
        metric_mode: 'approximate',
        measurements: approximateTextMetrics(normalized),
        warnings: [`font_metrics_approximate:${reason.slice(0, 180)}`],
      }
    }
  }
  return {
    metric_mode: 'approximate',
    measurements: approximateTextMetrics(normalized),
    warnings: ['font_metrics_approximate:CoreText is available only on macOS'],
  }
}
