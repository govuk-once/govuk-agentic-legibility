import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { formatReviewValue, initialReviewDraft } from '../src/lib/reviewValues.js';
import { submissionValue } from '../src/lib/submissionValue.js';

const answer = (value, kind = 'string', options = []) => ({ value, schema: { kind, options } });

test('review distinguishes zero, a skip, true and false', () => {
  assert.equal(formatReviewValue(answer('0')), '0');
  assert.equal(formatReviewValue(answer(0)), '0');
  assert.equal(formatReviewValue(answer('')), 'Not answered');
  assert.equal(formatReviewValue(answer(null)), 'Not answered');
  assert.equal(formatReviewValue(answer(false, 'boolean')), 'No');
  assert.equal(formatReviewValue(answer(true, 'boolean')), 'Yes');
  assert.equal(initialReviewDraft(answer(false, 'boolean')), 'false');
  assert.deepEqual(submissionValue(initialReviewDraft(answer(false, 'boolean')),
    { kind: 'boolean' }, false), { value: false });
});

test('review displays selection labels and explicit optional selection skip', () => {
  const options = [
    { value: 'a', label: 'A friend' },
    { value: 'b', label: 'A colleague' },
    { value: '__forms_skip__', label: 'Skip' },
  ];
  assert.equal(formatReviewValue(answer('a', 'select_one', options)), 'A friend');
  assert.equal(formatReviewValue(answer(['a', 'b'], 'select_many', options)), 'A friend, A colleague');
  assert.equal(formatReviewValue(answer('__forms_skip__', 'select_one', options)), 'Not answered');
  assert.equal(submissionValue('', { kind: 'select_one', options }, true).value, '__forms_skip__');
});

test('review shows safe upload metadata but never a file reference', () => {
  const upload = answer({ ref: 'opaque-secret', bytes: 128 }, 'file_ref');
  assert.equal(formatReviewValue(upload), 'Uploaded file (128 bytes)');
  assert.ok(!formatReviewValue(upload).includes('opaque-secret'));
});

test('review drafts do not mutate accepted array values', () => {
  const saved = answer(['a'], 'select_many');
  const draft = initialReviewDraft(saved);
  draft.push('b');
  assert.deepEqual(saved.value, ['a']);
});
