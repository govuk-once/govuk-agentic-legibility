import test from 'node:test';
import assert from 'node:assert/strict';
import { visibleSelectionOptions, toggleSelectedValues } from '../src/lib/selectionOptions.js';

test('select_one renders implicit None of the above but hides the separate skip sentinel', () => {
  const options = [
    {value:'resignation',label:'Resignation'},
    {value:'none_of_the_above',label:'None of the above'},
    {value:'__forms_skip__',label:'Skip this question'},
  ];
  assert.deepEqual(visibleSelectionOptions(options), options.slice(0, 2));
  assert.equal(visibleSelectionOptions(options)[1].label, 'None of the above');
});

test('None of the above is exclusive for checkbox entry and review edits', () => {
  const exclusive = ['none_of_the_above'];
  const ordinary = ['resignation', 'retirement'];
  assert.deepEqual(toggleSelectedValues(ordinary, 'none_of_the_above', true, exclusive),
    ['none_of_the_above']);
  assert.deepEqual(toggleSelectedValues(['none_of_the_above'], 'resignation', true, exclusive),
    ['resignation']);
  assert.deepEqual(toggleSelectedValues(['resignation'], 'retirement', true, exclusive),
    ['resignation', 'retirement']);
  assert.deepEqual(toggleSelectedValues(['none_of_the_above'], 'none_of_the_above', false, exclusive),
    []);
  assert.deepEqual(ordinary, ['resignation', 'retirement']); // immutable
});
