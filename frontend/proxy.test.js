import test from 'node:test'
import assert from 'node:assert/strict'
import configFactory from './vite.config.js'

test('vite proxy keeps the /api prefix for backend routes', () => {
  const config = configFactory({ mode: 'development' })
  const proxy = config.server.proxy['/api']

  assert.equal(proxy.target, 'http://localhost:8000')
  assert.equal(proxy.rewrite, undefined)
})
