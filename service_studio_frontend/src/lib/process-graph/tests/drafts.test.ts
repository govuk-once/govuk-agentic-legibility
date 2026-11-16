import { describe, expect, it } from 'vitest';
import type { Process } from '$lib/schema/workflow/process';
import type { WorkingProcess } from '$lib/schema/workflow/working-process';
import { isUndecidedRule } from '$lib/schema/workflow/placeholders';
import {
	addDraft,
	addDraftLine,
	canDraw,
	drawRealLine,
	noDrafts,
	promoteDrafts,
	removeFromDrafts,
	type DraftKind,
	type DraftSet,
	type Endpoint
} from '../drafts';

const finish = { state_type: 'end', status: 'success' };
const wait = (next: string) => ({ state_type: 'wait', duration: 'PT1S', next });

// Builds a process from a map of states. The cast is needed because each test gives only the keys it uses.
const build = (start: string, states: Record<string, unknown>) =>
	({ process_id: 'p', version: '0.1.0', vars: {}, start, states }) as unknown as Process;

const journey = () => build('a', { a: wait('b'), b: wait('end'), end: finish });

const state = (code: string): Endpoint => ({ kind: 'state', code });
const draftEnd = (id: string): Endpoint => ({ kind: 'draft', id });
const start: Endpoint = { kind: 'start' };

// Puts drafts on the canvas, and draws the lines given, in order, from one end to another.
function canvasWith(drafts: Array<[string, DraftKind]>, lines: Array<[Endpoint, Endpoint]> = []): DraftSet {
	let set = noDrafts;
	for (const [id, kind] of drafts) set = addDraft(set, { id, kind, position: { x: 0, y: 0 } });
	for (const [source, target] of lines) set = addDraftLine(set, source, target);
	return set;
}

describe('promoteDrafts', () => {
	it('makes the state a draft start leads to the start of the process', () => {
		const set = canvasWith([['s', 'start']], [[draftEnd('s'), state('b')]]);
		const promoted = promoteDrafts(journey(), set);
		expect(promoted.process.start).toBe('b');
		expect(promoted.set).toEqual(noDrafts);
	});

	it('ends the journey at the step that leads to a draft end', () => {
		const set = canvasWith([['e', 'end']], [[state('a'), draftEnd('e')]]);
		const promoted = promoteDrafts(journey(), set);
		const a = promoted.process.states.a;
		if (a.state_type !== 'wait' || a.next === undefined) throw new Error('a should still be a wait that continues somewhere');
		expect(promoted.process.states[a.next]).toMatchObject({ state_type: 'end' });
		// The step it led to before is left where it is.
		expect(promoted.process.states.b).toBeDefined();
		expect(promoted.set).toEqual(noDrafts);
		expect(promoted.becameStates).toEqual({ e: a.next });
	});

	it('waits for two ways on before a draft decision is real', () => {
		const process = build('a', { a: wait('x'), x: finish, y: finish, z: finish });
		const waiting = promoteDrafts(process, canvasWith([['d', 'condition']], [[state('a'), draftEnd('d')], [draftEnd('d'), state('y')]]));
		expect(waiting.set.drafts).toHaveLength(1);

		const ready = promoteDrafts(process, addDraftLine(waiting.set, draftEnd('d'), state('z')));
		const a = ready.process.states.a;
		if (a.state_type !== 'wait' || a.next === undefined) throw new Error('a should still be a wait that continues somewhere');
		const choice = ready.process.states[a.next];
		expect(choice).toMatchObject({ state_type: 'choice', default: 'z' });
		if (choice.state_type === 'choice') {
			expect(choice.rules.map((rule) => rule.next)).toEqual(['y']);
			expect(isUndecidedRule(choice.rules[0].when)).toBe(true);
		}
		expect(ready.set).toEqual(noDrafts);
		// The decision that was made is the one to show next.
		expect(ready.selectCode).toBe(a.next);
	});

	describe('a draft decision with a line to a draft end', () => {
		// A question with nothing after it, as one dropped from the palette is, and two steps it could lead to.
		const loose = () => build('a', { a: wait('fin'), fin: finish, q: { state_type: 'wait', duration: 'PT1S' }, x: wait('fin') });

		// The ways on of the decision that q now leads to, in order, with the kind of state each one is.
		function waysOn(process: WorkingProcess): string[] {
			const q = process.states.q;
			if (q.state_type !== 'wait' || q.next === undefined) throw new Error('q should now continue to a decision');
			const choice = process.states[q.next];
			if (choice.state_type !== 'choice') throw new Error('q should continue to a decision');
			return [...choice.rules.map((rule) => rule.next!), choice.default!].map((code) => process.states[code].state_type);
		}

		it.each([
			['a step then an end', [state('x'), draftEnd('e')], ['wait', 'end']],
			['an end then a step', [draftEnd('e'), state('x')], ['end', 'wait']]
		] as const)('makes both real when the decision leads to %s', (_label, targets, kinds) => {
			const lines: Array<[Endpoint, Endpoint]> = [[state('q'), draftEnd('d')], ...targets.map((target): [Endpoint, Endpoint] => [draftEnd('d'), target])];
			const promoted = promoteDrafts(loose(), canvasWith([['d', 'condition'], ['e', 'end']], lines));

			expect(promoted.set).toEqual(noDrafts);
			expect(waysOn(promoted.process)).toEqual(kinds);
		});

		it('makes two draft ends real with the decision', () => {
			const lines: Array<[Endpoint, Endpoint]> = [[state('q'), draftEnd('d')], [draftEnd('d'), draftEnd('e')], [draftEnd('d'), draftEnd('f')]];
			const promoted = promoteDrafts(loose(), canvasWith([['d', 'condition'], ['e', 'end'], ['f', 'end']], lines));

			expect(promoted.set).toEqual(noDrafts);
			expect(waysOn(promoted.process)).toEqual(['end', 'end']);
		});

		it('says which state each draft became, so each can be drawn where its draft was', () => {
			const lines: Array<[Endpoint, Endpoint]> = [[state('q'), draftEnd('d')], [draftEnd('d'), state('x')], [draftEnd('d'), draftEnd('e')]];
			const promoted = promoteDrafts(loose(), canvasWith([['d', 'condition'], ['e', 'end']], lines));

			const q = promoted.process.states.q;
			if (q.state_type !== 'wait' || q.next === undefined) throw new Error('q should now continue to a decision');
			expect(promoted.becameStates.d).toBe(q.next);
			expect(promoted.process.states[promoted.becameStates.e]).toMatchObject({ state_type: 'end' });
		});

		it('still waits while the decision has only one way on, an end', () => {
			const lines: Array<[Endpoint, Endpoint]> = [[state('q'), draftEnd('d')], [draftEnd('d'), draftEnd('e')]];
			const promoted = promoteDrafts(loose(), canvasWith([['d', 'condition'], ['e', 'end']], lines));
			expect(promoted.set.drafts.map((draft) => draft.kind)).toEqual(['condition', 'end']);
		});

		it('still waits while nothing leads to the decision', () => {
			const lines: Array<[Endpoint, Endpoint]> = [[draftEnd('d'), state('x')], [draftEnd('d'), draftEnd('e')]];
			const promoted = promoteDrafts(loose(), canvasWith([['d', 'condition'], ['e', 'end']], lines));
			expect(promoted.set.drafts).toHaveLength(2);
			expect(promoted.process).toEqual(loose());
		});
	});

	it('gives the reason and drops the lines when the process refuses', () => {
		// A draft end drawn from an end state cannot make that end end the journey.
		const set = canvasWith([['e', 'end']], [[state('end'), draftEnd('e')]]);
		const promoted = promoteDrafts(journey(), set);
		expect(promoted.reasons).toHaveLength(1);
		expect(promoted.set.lines).toEqual([]);
		expect(promoted.set.drafts).toHaveLength(1);
	});
});

describe('canDraw and drawRealLine', () => {
	const set = canvasWith([['s', 'condition'], ['e', 'end'], ['st', 'start']]);

	it('asks the process about a line between two states', () => {
		expect(canDraw(journey(), set, state('a'), state('end'))).toBe(true);
		expect(canDraw(journey(), set, state('a'), state('b'))).toBe(false);
		expect(canDraw(journey(), set, state('end'), state('a'))).toBe(false);
	});

	it('lets the start dot lead to a state other than the current start', () => {
		expect(canDraw(journey(), set, start, state('b'))).toBe(true);
		expect(canDraw(journey(), set, start, state('a'))).toBe(false);
	});

	it('does not let a line leave an end, arrive at a start, or go from the start dot to a draft end', () => {
		expect(canDraw(journey(), set, draftEnd('e'), state('a'))).toBe(false);
		expect(canDraw(journey(), set, state('a'), draftEnd('st'))).toBe(false);
		expect(canDraw(journey(), set, start, draftEnd('e'))).toBe(false);
	});

	it('lets a state lead to a draft decision, and refuses the start dot leading to one', () => {
		expect(canDraw(journey(), set, state('a'), draftEnd('s'))).toBe(true);
		expect(canDraw(journey(), set, start, draftEnd('s'))).toBe(false);
	});

	it('refuses a repeat of a line to a draft', () => {
		const drawn = addDraftLine(set, state('a'), draftEnd('s'));
		expect(canDraw(journey(), drawn, state('a'), draftEnd('s'))).toBe(false);
	});

	it('moves the start when a line is drawn from the start dot', () => {
		const result = drawRealLine(journey(), start, state('b'));
		expect(result.ok && result.process.start).toBe('b');
	});
});

describe('removeFromDrafts', () => {
	it('takes a draft out with every line that touched it', () => {
		const set = canvasWith([['s', 'condition']], [[state('a'), draftEnd('s')], [draftEnd('s'), state('b')]]);
		expect(removeFromDrafts(set, ['s'], [])).toEqual(noDrafts);
	});

	it('takes out a single line and leaves the draft', () => {
		const set = canvasWith([['s', 'condition']], [[state('a'), draftEnd('s')]]);
		const removed = removeFromDrafts(set, [], [set.lines[0].id]);
		expect(removed.drafts).toHaveLength(1);
		expect(removed.lines).toEqual([]);
	});
});
