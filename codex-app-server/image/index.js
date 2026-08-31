/** Narrow domain-tool adapter: retained image-search candidate -> local photo. */

import { submitWebImage } from './submit.js'

export const name = 'longwriter-image'

export function applyImage(registerTool, dependencies) {
  if (typeof registerTool !== 'function') throw new TypeError('image adapter requires registerTool')
  if (typeof dependencies?.workspace !== 'function') throw new TypeError('image adapter requires workspace resolver')
  for (const name of ['registerAsset', 'resolveVisualPlan', 'readAssetManifest', 'appendVisualPreflight']) {
    if (typeof dependencies?.[name] !== 'function') throw new TypeError(`image adapter requires ${name}`)
  }
  registerTool({
    name: 'image_submit',
    description: 'Download a public image URL and register it as a hash-bound assets/photos/* asset under an existing visual plan with kind photo. Call longwriter_search_images first when you still need to discover a URL. After registration, pass the returned asset id and preflight id to inspect_visual before citing the local photo path. Never hotlink a remote URL into article.md.',
    parameters: {
      image_url: { type: 'string', required: true, description: 'Public HTTP(S) image URL to download and register locally.' },
      caption: { type: 'string', required: true, description: 'Concise publication caption.' },
      alt_text: { type: 'string', required: true, description: 'Accessible description of the photo.' },
      visual_plan_id: { type: 'string', required: true, description: 'Existing project.json visual_contract figure id with kind photo.' },
      used_in: { type: 'json', required: true, description: 'Article section ids; must include the visual plan section.' },
      supersedes_asset_id: { type: 'string', description: 'Required for a new revision after an earlier photo for the same plan.' },
      id: { type: 'string', description: 'Optional safe photo asset id.' },
      source: { type: 'string', description: 'Optional source label; defaults to web_image.' },
      licence: { type: 'string', description: 'Optional licence label; defaults to source_url.' },
    },
    isConcurrencySafe: () => false,
    execute(args, exec) {
      return submitWebImage(dependencies.workspace(exec), args, {
        registerAsset: dependencies.registerAsset,
        resolveVisualPlan: dependencies.resolveVisualPlan,
        readAssetManifest: dependencies.readAssetManifest,
        appendVisualPreflight: dependencies.appendVisualPreflight,
        fetch: dependencies.fetch,
        signal: exec.signal,
      })
    },
  })
}
