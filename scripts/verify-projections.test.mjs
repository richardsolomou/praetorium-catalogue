import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

const first = { projection: 'canonical', sha256: 'a'.repeat(64) }
const second = { projection: 'edition:rules', sha256: 'b'.repeat(64) }

const compare = (source, runtime) => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'catalogue-projections-'))
  try {
    const files = ['source', 'runtime'].map((name, index) => {
      const file = path.join(directory, name)
      fs.writeFileSync(file, [source, runtime][index].map((record) => JSON.stringify(record)).join('\n'))
      return file
    })
    return spawnSync(process.execPath, [new URL('./verify-projections.mjs', import.meta.url).pathname, ...files]).status
  } finally {
    fs.rmSync(directory, { recursive: true, force: true })
  }
}

test('accepts identical projections in a different order with diagnostic records', () => {
  assert.equal(compare([{ stage: 'ready' }, first, second], [second, first]), 0)
})

test('rejects changed runtime data', () => {
  assert.notEqual(compare([first], [{ ...first, sha256: 'c'.repeat(64) }]), 0)
})

test('rejects an omitted runtime projection', () => {
  assert.notEqual(compare([first, second], [first]), 0)
})

test('rejects duplicate projection identities', () => {
  assert.notEqual(compare([first, first], [first]), 0)
})

test('rejects empty diagnostic output on both sides', () => {
  assert.notEqual(compare([{ stage: 'ready' }], [{ stage: 'ready' }]), 0)
})
