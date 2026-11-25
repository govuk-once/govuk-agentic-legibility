import test from 'node:test';
import assert from 'node:assert/strict';
import { createProposalAttemptGate } from '../src/lib/proposalAttemptGate.js';

test('the same unanswered question cannot restart automatic mode after refresh', () => {
  const gate = createProposalAttemptGate();
  assert.equal(gate.claim('form6', 'token-1', 'auto'), true);
  assert.equal(gate.claim('form6', 'token-1', 'auto'), false);
  // The browser may refresh the awaiting input without its token changing.
  assert.equal(gate.claim('form6', 'token-1', 'auto'), false);
  assert.equal(gate.claim('form6', 'token-2', 'auto'), true);
});

test('after manual submission, the new question can start a fresh automatic pass', () => {
  const gate = createProposalAttemptGate();
  assert.equal(gate.claim('form6', 'token-1', 'auto'), true);
  assert.equal(gate.claim('form6', 'token-2', 'auto'), true);
  assert.equal(gate.claim('form6', 'token-2', 'auto'), false);
  // Manual submission advances Temporal to a new token.
  assert.equal(gate.claim('form6', 'token-3', 'auto'), true);
});

test('policy changes, retry and a new session are handled explicitly', () => {
  const gate = createProposalAttemptGate();
  assert.equal(gate.claim('form6', 'token-1', 'manual'), false);
  assert.equal(gate.claim('form6', 'token-1', 'auto'), true);
  assert.equal(gate.claim('form6', 'token-1', 'confirm'), true);
  gate.retry('form6', 'token-1', 'auto');
  assert.equal(gate.claim('form6', 'token-1', 'auto'), true);
  assert.equal(gate.claim('another-session', 'token-1', 'auto'), true);
});
