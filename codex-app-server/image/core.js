/** Bounded web-image download: public HTTP(S), magic sniff, size cap. */

export const MAX_PHOTO_BYTES = 8 * 1024 * 1024
export const MIN_PHOTO_EDGE = 32
export const PHOTO_EXTS = new Set(['.png', '.jpg', '.jpeg', '.webp'])

const PRIVATE_HOST = /^(localhost|0\.0\.0\.0)$/i
const PRIVATE_V4 = /^(127\.|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[0-1])\.)/

export function assertPublicHttpUrl(value, name = 'image_url') {
  let url
  try {
    url = new URL(String(value ?? ''))
  } catch {
    throw new TypeError(`${name} must be an absolute HTTP(S) URL`)
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new TypeError(`${name} must be an absolute HTTP(S) URL`)
  }
  const host = url.hostname
  if (PRIVATE_HOST.test(host) || host.endsWith('.local') || PRIVATE_V4.test(host) || host.includes(':')) {
    throw new TypeError(`${name} must not target a private or local host`)
  }
  return url.toString()
}

export function sniffImage(bytes, contentType) {
  const declared = String(contentType ?? '').split(';')[0].trim().toLowerCase()
  if (bytes?.byteLength >= 8 && bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47) {
    return { mime: 'image/png', ext: '.png' }
  }
  if (bytes?.byteLength >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) {
    return { mime: 'image/jpeg', ext: '.jpg' }
  }
  if (
    bytes?.byteLength >= 12
    && bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46
    && bytes[8] === 0x57 && bytes[9] === 0x45 && bytes[10] === 0x42 && bytes[11] === 0x50
  ) {
    return { mime: 'image/webp', ext: '.webp' }
  }
  if (declared === 'image/png') return { mime: 'image/png', ext: '.png' }
  if (declared === 'image/jpeg' || declared === 'image/jpg') return { mime: 'image/jpeg', ext: '.jpg' }
  if (declared === 'image/webp') return { mime: 'image/webp', ext: '.webp' }
  return null
}

export function pngSize(bytes) {
  if (!bytes || bytes.byteLength < 24) return null
  const ihdr = Buffer.from(bytes).subarray(12, 16).toString('ascii')
  if (ihdr !== 'IHDR') return null
  return {
    width: Buffer.from(bytes).readUInt32BE(16),
    height: Buffer.from(bytes).readUInt32BE(20),
  }
}

export function findRetainedCandidate(manifest, imageUrl) {
  const wanted = assertPublicHttpUrl(imageUrl)
  const receipts = Array.isArray(manifest?.image_searches) ? manifest.image_searches : []
  for (const receipt of receipts) {
    const candidates = Array.isArray(receipt?.candidates) ? receipt.candidates : []
    const match = candidates.find(item => item?.image_url === wanted)
    if (match) return { receipt, candidate: match }
  }
  return null
}

export async function downloadPublicImage(imageUrl, { fetchImpl, referer, signal } = {}) {
  const url = assertPublicHttpUrl(imageUrl)
  const fetchFn = fetchImpl ?? globalThis.fetch
  if (typeof fetchFn !== 'function') throw new Error('image download requires fetch')
  const headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) LongMDWriter/0.2',
    Accept: 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
  }
  if (referer) headers.Referer = referer
  const response = await fetchFn(url, { headers, signal, redirect: 'follow' })
  if (!response?.ok) throw new Error(`image download failed: HTTP ${response?.status ?? 'unknown'}`)
  const buffer = Buffer.from(await response.arrayBuffer())
  if (buffer.byteLength === 0) throw new Error('image download returned empty bytes')
  if (buffer.byteLength > MAX_PHOTO_BYTES) throw new Error(`image download exceeds ${MAX_PHOTO_BYTES} bytes`)
  const contentType = typeof response.headers?.get === 'function' ? response.headers.get('content-type') : null
  const sniffed = sniffImage(buffer, contentType)
  if (!sniffed) throw new Error('downloaded bytes are not a supported raster image')
  if (sniffed.mime === 'image/png') {
    const size = pngSize(buffer)
    if (size && (size.width < MIN_PHOTO_EDGE || size.height < MIN_PHOTO_EDGE)) {
      throw new Error(`photo must be at least ${MIN_PHOTO_EDGE}px on each edge`)
    }
  }
  return { bytes: buffer, mime: sniffed.mime, ext: sniffed.ext, url }
}
