import { redirectRoutes, routesInto } from './edit-process';
import { hasNext, replaceState, withNext, withoutNext } from './edit-state';
import type { WorkingProcess } from './working-process';

/*
	Moving a step up or down changes the journey itself. The steps are not kept in a list, so there is no
	list to reorder: a step moves by swapping places with the step it continues to, which rewires the routes
	around the pair. The step numbers follow the routes, so they change by themselves.

	1. A step can swap with any step it continues to. Nothing is refused to keep the journey working, because a
	   journey is allowed to be rearranged freely and is checked before it is passed on.
	2. A step cannot move when there is no step on that side to swap with: it continues to a decision, an end
	   or nothing, or no single step leads to it.
	3. An editor can name a state that travels in front of a step, such as the assign that saves an answer before
	   the next input. The two then move as one block, and a step moving past them passes both.
*/

/**
 * Finds the state that travels in front of a step, or nothing when the step moves on its own. An editor that keeps
 * two states together gives a function of this shape to every function in this file.
 */
export type AttachedBefore = (process: WorkingProcess, code: string) => string | undefined;

const nothingAttached: AttachedBefore = () => undefined;

// The states that move together, named by the first and the last. A step on its own is both.
type Block = { first: string; last: string };

// The block a step moves in: the step, with the state that travels in front of it when there is one.
function blockOf(process: WorkingProcess, code: string, attachedBefore: AttachedBefore): Block {
	return { first: attachedBefore(process, code) ?? code, last: code };
}

/**
 * Finds the block that a block would swap places with if it moved down, which is the block it continues to.
 * Returns nothing when there is no step there to swap with, so one check serves both the button and the move itself.
 */
function laterBlock(process: WorkingProcess, block: Block, attachedBefore: AttachedBefore): Block | undefined {
	const last = process.states[block.last];
	// A step with nothing after it has no neighbour to swap with.
	if (!last || !hasNext(last) || last.next === undefined) return undefined;

	const afterCode = last.next;
	const after = process.states[afterCode];
	// A decision or an end is not a step, so there is nothing to swap with.
	if (!after || !hasNext(after)) return undefined;

	// The state after may travel in front of the step it continues to, and then the two are passed together.
	const travelsWith = after.next !== undefined && attachedBefore(process, after.next) === afterCode ? after.next : undefined;
	const later: Block = { first: afterCode, last: travelsWith ?? afterCode };

	// The later block must end in a step, and must be made of other states than the block that is moving.
	const laterLast = process.states[later.last];
	if (!laterLast || !hasNext(laterLast)) return undefined;
	const moving = new Set([block.first, block.last]);
	if (moving.has(later.first) || moving.has(later.last)) return undefined;

	// Two blocks that continue to each other have no order to change.
	return laterLast.next === block.first ? undefined : later;
}

/**
 * Finds the block that a step would swap places with if it moved up, which is the block that leads to it.
 * Returns nothing when no single step leads to it.
 */
function earlierBlock(process: WorkingProcess, code: string, attachedBefore: AttachedBefore): Block | undefined {
	const block = blockOf(process, code, attachedBefore);

	// The steps that continue to the block. A decision that leads to it is not a step, so it does not count.
	const before = routesInto(process, block.first).filter(({ source, route }) => route.kind === 'next' && source !== block.last);
	if (before.length !== 1) return undefined;

	const earlier = blockOf(process, before[0].source, attachedBefore);
	return laterBlock(process, earlier, attachedBefore)?.last === code ? earlier : undefined;
}

/**
 * Returns a copy of the process in which a block has swapped places with the block it continues to. Everything
 * that led to the first block now leads to the second, the second continues to the first, and the first continues
 * to where the second went.
 */
function swapBlocks(process: WorkingProcess, first: Block, second: Block): WorkingProcess {
	// Both ends are read before anything is redirected, because the swap rebuilds them from these copies.
	const firstLast = process.states[first.last];
	const secondLast = process.states[second.last];
	if (!hasNext(secondLast)) return process;

	// Everything that led to the first block, including the start of the process, now leads to the second.
	const redirected = redirectRoutes(process, first.first, second.first);

	// The second block comes first and continues to the first block, and its other routes are left as they were.
	const secondFirst = replaceState(redirected, second.last, withNext(secondLast, first.first));
	// The first block comes second and continues to wherever the second block used to go, which may be nowhere yet.
	return replaceState(secondFirst, first.last, secondLast.next === undefined ? withoutNext(firstLast) : withNext(firstLast, secondLast.next));
}

/**
 * Tells whether a step can move down, so the panel only offers a button that will work.
 */
export function canMoveLater(process: WorkingProcess, code: string, attachedBefore: AttachedBefore = nothingAttached): boolean {
	return laterBlock(process, blockOf(process, code, attachedBefore), attachedBefore) !== undefined;
}

/**
 * Tells whether a step can move up, so the panel only offers a button that will work.
 */
export function canMoveEarlier(process: WorkingProcess, code: string, attachedBefore: AttachedBefore = nothingAttached): boolean {
	return earlierBlock(process, code, attachedBefore) !== undefined;
}

/**
 * Returns a copy of the process in which a step has swapped places with the step after it. If there is no step
 * to swap with, the process is returned as it is.
 */
export function moveLater(process: WorkingProcess, code: string, attachedBefore: AttachedBefore = nothingAttached): WorkingProcess {
	const block = blockOf(process, code, attachedBefore);
	const later = laterBlock(process, block, attachedBefore);
	return later ? swapBlocks(process, block, later) : process;
}

/**
 * Returns a copy of the process in which a step has swapped places with the step before it. This is the
 * earlier step moving down, so it uses the same swap. If there is no step to swap with, the process is returned
 * as it is.
 */
export function moveEarlier(process: WorkingProcess, code: string, attachedBefore: AttachedBefore = nothingAttached): WorkingProcess {
	const earlier = earlierBlock(process, code, attachedBefore);
	return earlier ? swapBlocks(process, earlier, blockOf(process, code, attachedBefore)) : process;
}
