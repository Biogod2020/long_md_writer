import assert from 'node:assert/strict'
import test from 'node:test'

import { renderSvgToPng } from '../svg/renderer.js'

const SVG = [
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">',
  '<rect width="20" height="20" fill="#ffffff"/>',
  '<circle cx="10" cy="10" r="5" fill="#268bd2"/>',
  '</svg>',
].join('\n')

test('renders a safe SVG to a nonempty PNG through an available local backend', async () => {
  const rendered = await renderSvgToPng(SVG)
  assert.ok(rendered)
  assert.ok(['resvg-js', 'cairosvg'].includes(rendered.backend))
  assert.ok(rendered.png.byteLength > 8)
  assert.deepEqual([...rendered.png.slice(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10])
})
