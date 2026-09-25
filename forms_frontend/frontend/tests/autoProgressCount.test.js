import test from 'node:test';
import assert from 'node:assert/strict';
import { cumulativeAnsweredCount } from '../src/lib/autoProgressCount.js';

test('form 6 progress includes manual answers without calling them automatic', () => {
  let completed = 7; // First automatic pass finished.
  completed = 8;     // Q8 was accepted manually; the next pass starts at 8.
  completed = cumulativeAnsweredCount(completed, {type:'waiting', answered_count:8});
  completed = cumulativeAnsweredCount(completed, {type:'step', answered_count:9});
  assert.equal(completed, 9);
  completed = cumulativeAnsweredCount(completed, {type:'step', answered_count:10});
  assert.equal(completed, 10);
  assert.equal(cumulativeAnsweredCount(completed, {type:'done', answered_count:9}), 10);
  assert.equal(cumulativeAnsweredCount(completed, {type:'done', answered_count:10}), 10);
});
