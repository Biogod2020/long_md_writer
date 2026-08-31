import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

export function loadLocalEnv(file = path.join(packageRoot, '.env')) {
  try {
    process.loadEnvFile(file)
    return true
  } catch (error) {
    if (error.code === 'ENOENT') return false
    throw error
  }
}
