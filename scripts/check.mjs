import assert from 'node:assert/strict'
import fs from 'node:fs'

const compiler = JSON.parse(fs.readFileSync('compiler.json', 'utf8'))
assert.match(compiler.repository, /^[\w.-]+\/[\w.-]+$/)
assert.match(compiler.revision, /^[a-f0-9]{40}$/)
for (const name of [
  'sources',
  'composition',
  'revocations',
  'accepted-coverage-losses',
  'retained-profile-build',
  'retained-roster-rules',
  'retired-ids',
  'roster-migrations',
])
  JSON.parse(fs.readFileSync(`catalogue/${name}.json`, 'utf8'))
