import assert from 'node:assert/strict'
import fs from 'node:fs'

const projections = (file) => {
  const records = fs
    .readFileSync(file, 'utf8')
    .trim()
    .split('\n')
    .map((line) => JSON.parse(line))
    .filter((record) => record.projection)
  assert.ok(records.length > 0, 'No projection hashes were produced')
  const values = Object.fromEntries(records.map(({ projection, sha256 }) => [projection, sha256]))
  assert.equal(Object.keys(values).length, records.length, 'Duplicate projection hashes')
  for (const digest of Object.values(values)) assert.match(digest, /^[a-f0-9]{64}$/)
  return values
}

assert.deepEqual(projections(process.argv[2]), projections(process.argv[3]), 'Source and runtime projections differ')
console.log('Source and runtime projection hashes match')
