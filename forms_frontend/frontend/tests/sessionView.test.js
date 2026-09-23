import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { sessionView, waitForCompletion, reviewAcknowledged } from '../src/lib/sessionView.js';

test('completed form 6 goes to review, never the initial question', () => {
  const state = { status: 'COMPLETED', review_required: true, awaiting: null,
    answer_history: Array.from({ length: 11 }, (_, i) => ({ state_id: `${i}` })) };
  assert.equal(sessionView('form', state), 'review');
  assert.equal(sessionView('complete', state), 'review');
  assert.equal(sessionView('review', { ...state, review_required: false }), 'complete');
  assert.equal(sessionView('review', { status: 'RUNNING', awaiting: { token: 'new' } }), 'form');
});

test('terminal event refuses an old first question until Temporal confirms completion', () => {
  const first = { status: 'RUNNING', awaiting: { token: 'first-token' } };
  assert.equal(waitForCompletion(first, true), true);
  assert.equal(waitForCompletion({ status: 'ADVANCING', awaiting: null }, true), true);
  assert.equal(waitForCompletion({ status: 'COMPLETED', awaiting: null }, true), false);
  assert.equal(waitForCompletion(first, false, 'first-token'), true);
  assert.equal(waitForCompletion(first, false, 'previous-token'), false);
});

test('review preference must be acknowledged by the API at session start', () => {
  assert.equal(reviewAcknowledged(true, true), true);
  assert.equal(reviewAcknowledged(false, false), true);
  assert.equal(reviewAcknowledged(true, false), false);
  assert.equal(reviewAcknowledged(true, undefined), false);
});
