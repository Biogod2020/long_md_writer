/** Register a retained image-search candidate as a hash-bound local photo. */

import { createHash } from 'node:crypto'
import { spawn } from 'node:child_process'
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'

import { downloadPublicImage, findRetainedCandidate } from './core.js'

function requiredText(value, name) {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new TypeError(`${name} must be a non-empty string`)
  }
  return value.trim()
}

function requireDependency(dependencies, name) {
  if (typeof dependencies?.[name] !== 'function') {
    throw new TypeError(`image submission requires ${name}`)
  }
  return dependencies[name]
}

async function jpegOrWebpToPng(bytes, ext) {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'longwriter-photo-'))
  const source = path.join(directory, `source${ext}`)
  const target = path.join(directory, 'preview.png')
  try {
    await writeFile(source, bytes)
    await new Promise((resolve, reject) => {
      const child = spawn('sips', ['-s', 'format', 'png', source, '--out', target], { stdio: 'ignore' })
      child.on('error', reject)
      child.on('close', code => {
        if (code === 0) resolve()
        else reject(new Error(`sips failed with exit code ${code}`))
      })
    })
    return await readFile(target)
  } finally {
    await rm(directory, { recursive: true, force: true })
  }
}

async function previewPng(downloaded) {
  if (downloaded.mime === 'image/png') return downloaded.bytes
  return jpegOrWebpToPng(downloaded.bytes, downloaded.ext)
}

export async function submitWebImage(workspace, input, dependencies = {}) {
  const registerAsset = requireDependency(dependencies, 'registerAsset')
  const resolveVisualPlan = requireDependency(dependencies, 'resolveVisualPlan')
  const readAssetManifest = requireDependency(dependencies, 'readAssetManifest')
  const appendVisualPreflight = requireDependency(dependencies, 'appendVisualPreflight')
  const plan = await resolveVisualPlan(workspace, requiredText(input?.visual_plan_id, 'visual_plan_id'))
  if (plan.kind !== 'photo') throw new Error('image_submit requires a visual plan with kind photo')
  const usedIn = Array.isArray(input?.used_in) ? input.used_in : []
  if (!usedIn.includes(plan.section_id)) {
    throw new TypeError(`used_in must include the planned section ${plan.section_id}`)
  }
  const imageUrl = requiredText(input?.image_url, 'image_url')
  const manifest = await readAssetManifest(workspace)
  const matched = findRetainedCandidate(manifest, imageUrl)
  const downloaded = await downloadPublicImage(matched?.candidate?.image_url ?? imageUrl, {
    fetchImpl: dependencies.fetch,
    referer: matched?.candidate?.source_page_url,
    signal: dependencies.signal,
  })
  const digest = createHash('sha256').update(downloaded.bytes).digest('hex')
  const id = input?.id ? requiredText(input.id, 'id') : `photo-${digest.slice(0, 12)}`
  const registered = await registerAsset(workspace, {
    id,
    source: requiredText(input?.source ?? 'web_image', 'source'),
    path: `assets/photos/${id}${downloaded.ext}`,
    caption: requiredText(input?.caption, 'caption'),
    alt_text: requiredText(input?.alt_text, 'alt_text'),
    provenance: `web_image:${downloaded.url}`,
    licence: requiredText(input?.licence ?? 'source_url', 'licence'),
    used_in: usedIn,
    visual_plan_id: plan.id,
    supersedes_asset_id: input?.supersedes_asset_id,
    bytes: downloaded.bytes,
  })
  const previewBytes = await previewPng(downloaded)
  const previewId = `preview-${registered.sha256.slice(0, 20)}`
  const preview = await registerAsset(workspace, {
    id: previewId,
    source: 'tool',
    path: `assets/reviews/${previewId}.png`,
    caption: 'Photo review preview',
    alt_text: 'Raster preview of a retained web photo.',
    provenance: 'derived:photo-preflight',
    licence: 'generated_internal',
    used_in: [],
    derivative_of: {
      asset_id: registered.entry.id,
      asset_sha256: registered.sha256,
      purpose: 'photo-preview',
    },
    bytes: previewBytes,
  })
  const preflight = await appendVisualPreflight(workspace, {
    asset_id: registered.entry.id,
    asset_sha256: registered.sha256,
    visual_plan_id: plan.id,
    preview_asset_id: preview.entry.id,
    preview_sha256: preview.sha256,
    metric_mode: 'photo',
    renderer: downloaded.mime === 'image/png' ? 'identity-png' : 'sips-png',
    passed: true,
    issues: [],
    warnings: [],
  })
  return {
    status: 'registered',
    asset: {
      id: registered.entry.id,
      path: registered.path,
      sha256: registered.sha256,
      visual_plan_id: plan.id,
    },
    preview: {
      id: preview.entry.id,
      path: preview.path,
      sha256: preview.sha256,
    },
    preflight,
    candidate: matched
      ? {
        image_url: matched.candidate.image_url,
        source_page_url: matched.candidate.source_page_url,
        receipt_id: matched.receipt.id,
      }
      : {
        image_url: downloaded.url,
        source_page_url: null,
        receipt_id: null,
      },
  }
}
