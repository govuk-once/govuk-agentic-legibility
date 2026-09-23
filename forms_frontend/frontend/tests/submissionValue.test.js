import test from 'node:test';
import assert from 'node:assert/strict';
import { submissionValue } from '../src/lib/submissionValue.js';

const optionalNumber = { kind: 'string', allow_skip: true, default: '' };
test('0 is a real answer; skip is a distinct empty string', () => {
  assert.deepEqual(submissionValue('0', optionalNumber, true), { value: '0' });
  assert.deepEqual(submissionValue(0, optionalNumber, true), { value: '0' });
  assert.deepEqual(submissionValue('', optionalNumber, true), { value: '' });
  assert.deepEqual(submissionValue(null, optionalNumber, true), { value: '' });
});
test('boolean radio values are native booleans, including false', () => {
  assert.deepEqual(submissionValue('true', {kind:'boolean'}, false), { value: true });
  assert.deepEqual(submissionValue('false', {kind:'boolean'}, false), { value: false });
  assert.deepEqual(submissionValue(false, {kind:'boolean'}, false), { value: false });
});
test('optional select_one uses explicit SFSM skip option', () => {
  const schema = {kind:'select_one', allow_skip:true, options:[
    {value:'alpha',label:'Alpha'}, {value:'__forms_skip__',label:'Skip'}]};
  assert.deepEqual(submissionValue('', schema, true), {value:'__forms_skip__'});
  assert.deepEqual(submissionValue('alpha', schema, true), {value:'alpha'});
});
test('file skips use null, select_many skips use empty arrays and required input rejects empties', () => {
  assert.deepEqual(submissionValue(null, {kind:'file_ref',allow_skip:true}, true), {value:null});
  assert.deepEqual(submissionValue('', {kind:'select_many',allow_skip:true}, true), {value:[]});
  assert.deepEqual(submissionValue('', {kind:'string'}, false), {error:'This field is required'});
});
