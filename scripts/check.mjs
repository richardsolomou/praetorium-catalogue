import assert from 'node:assert/strict'
import fs from 'node:fs'

const compiler = JSON.parse(fs.readFileSync('compiler.json', 'utf8'))
assert.match(compiler.repository, /^[\w.-]+\/[\w.-]+$/)
assert.match(compiler.revision, /^[a-f0-9]{40}$/)
for (const name of ['sources', 'composition', 'revocations']) JSON.parse(fs.readFileSync(`catalogue/${name}.json`, 'utf8'))
