import { addBranch, drawLine, endJourneyAt, type EditResult } from '$lib/schema/workflow/edit-journey';
import { setStart } from '$lib/schema/workflow/edit-process';
import type { WorkingProcess } from '$lib/schema/workflow/working-process';

/*
	Shapes placed on the canvas that are not part of the process yet. A start needs a state to lead to, an end
	needs a state leading to it, and a decision needs a state leading in and ways on, so none of them can be
	written to the process on their own. They stay on the canvas as drafts, with the lines drawn to them, until
	enough is joined up. Then the change is made to the process and the draft is replaced by the real thing.
	A step is not a draft. It is added to the process as soon as it is dropped, because a step with nothing after
	it is allowed while a journey is being built.

	1. A draft start is promoted once a line leads from it to a state, which becomes the start of the process.
	2. A draft end is promoted once a line leads to it from a state, which then ends the journey there.
	3. A draft decision is promoted once a state leads to it and it leads to two or more states, which become
	   ways on from that state.
	4. Promoting one draft can make another ready, so promotion repeats until nothing more changes.
*/

export type DraftKind = 'condition' | 'start' | 'end';

// One shape placed on the canvas that is not yet in the process. The id is made up for the canvas only.
export type Draft = { id: string; kind: DraftKind; position: { x: number; y: number } };

// One end of a line: the start dot, a state of the process, or a draft.
export type Endpoint = { kind: 'start' } | { kind: 'state'; code: string } | { kind: 'draft'; id: string };

// A line drawn to or from a draft. A line between two real ends is made to the process at once and never kept.
export type DraftLine = { id: string; source: Endpoint; target: Endpoint };

export type DraftSet = { drafts: Draft[]; lines: DraftLine[] };

export const noDrafts: DraftSet = { drafts: [], lines: [] };

// Where a draft is in the result of promoting: the process, what is left, the new state to show, and any reasons.
export type Promotion = { process: WorkingProcess; set: DraftSet; selectCode?: string; reasons: string[] };

/**
 * Makes a name for a draft. It is only used on the canvas, so it needs to be unique and nothing more.
 */
export function newDraftId(): string {
	return `draft-${crypto.randomUUID()}`;
}

/**
 * Tells whether two ends of a line are the same thing.
 */
export function sameEndpoint(a: Endpoint, b: Endpoint): boolean {
	if (a.kind !== b.kind) return false;
	if (a.kind === 'state' && b.kind === 'state') return a.code === b.code;
	if (a.kind === 'draft' && b.kind === 'draft') return a.id === b.id;
	return true;
}

/**
 * Returns a copy of the set with a draft added.
 */
export function addDraft(set: DraftSet, draft: Draft): DraftSet {
	return { ...set, drafts: [...set.drafts, draft] };
}

/**
 * Returns a copy of the set with a line drawn between two ends, at least one of which is a draft. A line
 * that is already there is not added twice.
 */
export function addDraftLine(set: DraftSet, source: Endpoint, target: Endpoint): DraftSet {
	if (set.lines.some((line) => sameEndpoint(line.source, source) && sameEndpoint(line.target, target))) return set;
	return { ...set, lines: [...set.lines, { id: `${newDraftId()}-line`, source, target }] };
}

/**
 * Returns a copy of the set without some drafts and some lines. A line that touches a draft that goes is
 * taken out with it.
 */
export function removeFromDrafts(set: DraftSet, draftIds: string[], lineIds: string[]): DraftSet {
	const gone = new Set(draftIds);
	const touchesGone = (end: Endpoint) => end.kind === 'draft' && gone.has(end.id);

	return {
		drafts: set.drafts.filter((draft) => !gone.has(draft.id)),
		lines: set.lines.filter((line) => !lineIds.includes(line.id) && !touchesGone(line.source) && !touchesGone(line.target))
	};
}

/**
 * Tells whether a line may be drawn from one end to another. Lines between two states are asked of the
 * process itself, so a line that would not be accepted never snaps onto a shape. A line to or from a draft
 * only has to make sense for the shape: nothing leaves an end, nothing arrives at a start, and the start dot
 * only leads to a step.
 */
export function canDraw(process: WorkingProcess, set: DraftSet, source: Endpoint, target: Endpoint): boolean {
	if (sameEndpoint(source, target) || target.kind === 'start') return false;

	const kindOf = (end: Endpoint) => (end.kind === 'draft' ? set.drafts.find((draft) => draft.id === end.id)?.kind : undefined);
	if (kindOf(source) === 'end' || kindOf(target) === 'start') return false;
	// A line from the start dot only means something when it leads to a state.
	if (source.kind === 'start' && target.kind === 'draft') return false;

	if (source.kind === 'state' && target.kind === 'state') return drawLine(process, source.code, target.code).ok;
	if (source.kind === 'start' && target.kind === 'state') return process.start !== target.code;

	// A line between a state and a draft waits on the canvas, so only a repeat is refused.
	return !set.lines.some((line) => sameEndpoint(line.source, source) && sameEndpoint(line.target, target));
}

/**
 * Draws a line between two ends that are both in the process. From the start dot it moves the start of the
 * process, and between two states it is drawn the same way as any other line.
 */
export function drawRealLine(process: WorkingProcess, source: Endpoint, target: Endpoint): EditResult {
	if (target.kind !== 'state') return { ok: false, reason: 'A line must join two steps.' };
	if (source.kind === 'start') return { ok: true, process: setStart(process, target.code) };
	if (source.kind === 'state') return drawLine(process, source.code, target.code);
	return { ok: false, reason: 'A line must join two steps.' };
}

// The codes of the states a list of lines leads to, or comes from, without repeats and in the order drawn.
function stateCodes(ends: Endpoint[]): string[] {
	return [...new Set(ends.flatMap((end) => (end.kind === 'state' ? [end.code] : [])))];
}

/**
 * Makes every draft that has enough joined to it part of the process, and replaces each with the real
 * thing. Lines that led to a draft that has become a state now lead to that state, so the drafts they came
 * from can be promoted next. A draft that cannot be promoted because the process refuses the change keeps its
 * place, loses the lines that were refused, and the reason is returned.
 */
export function promoteDrafts(process: WorkingProcess, set: DraftSet): Promotion {
	let current = process;
	let remaining = set;
	let selectCode: string | undefined;
	const reasons: string[] = [];

	// Promoting one draft can make another ready, so each pass starts again from the first draft.
	let changed = true;
	while (changed) {
		changed = false;

		for (const draft of remaining.drafts) {
			const outgoing = remaining.lines.filter((line) => line.source.kind === 'draft' && line.source.id === draft.id);
			const incoming = remaining.lines.filter((line) => line.target.kind === 'draft' && line.target.id === draft.id);
			const targets = stateCodes(outgoing.map((line) => line.target));
			const sources = stateCodes(incoming.map((line) => line.source));

			let result: EditResult | undefined;
			if (draft.kind === 'start' && targets.length > 0) result = { ok: true, process: setStart(current, targets[0]) };
			if (draft.kind === 'end' && sources.length > 0) result = endJourneyAt(current, sources[0]);
			if (draft.kind === 'condition' && sources.length > 0 && targets.length >= 2) result = addBranch(current, sources[0], targets);
			if (!result) continue;

			if (!result.ok) {
				// The refused lines are dropped so the same reason is not given again. The draft stays for another try.
				reasons.push(result.reason);
				const refused = new Set([...incoming, ...outgoing].map((line) => line.id));
				remaining = removeFromDrafts(remaining, [], [...refused]);
				changed = true;
				break;
			}

			current = result.process;
			// A decision that has just been made is shown, so its ways on can be set straight away.
			if (draft.kind === 'condition') selectCode = result.code;

			// The draft is replaced by the real thing, so it goes with every line that touched it.
			remaining = removeFromDrafts(remaining, [draft.id], []);
			changed = true;
			break;
		}
	}

	return { process: current, set: remaining, selectCode, reasons };
}
