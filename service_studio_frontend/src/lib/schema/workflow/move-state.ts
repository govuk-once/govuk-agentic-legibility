import { routesInto } from '$lib/schema/workflow/edit-process';
import { hasNext, nothingYet, replaceState, withChoiceTargets, withoutNext } from '$lib/schema/workflow/edit-state';
import { journeyOrder } from '$lib/schema/workflow/journey-order';
import { routesOf, withRouteTarget } from '$lib/schema/workflow/routes';
import type { WorkingProcess, WorkingState } from '$lib/schema/workflow/working-process';

/*
	Moving a step up or down changes the journey itself. The steps are not kept in a list, so there is no
	list to reorder: a step moves by swapping places with the step it continues to, which rewires the routes
	around the pair. The step numbers follow the routes, so they change by themselves.

	1. A step moves as part of a block. An editor says which states travel together, such as the assign that
	   saves an answer before the next input, or every state of a module. On its own a step is a block of one.
	2. A block can only move when it has one way in and one way out. The way in is the state that everything
	   outside the block leads to. The way out is the one onward route that leaves the block, which may lead
	   nowhere yet. A block that branches, such as a decision, or one that ends the journey, cannot move, and
	   nothing can swap places with it.
	3. A block swaps with the block its way out leads to. Nothing is refused to keep the journey working, because a
	   journey is allowed to be rearranged freely and is checked before it is passed on.
	4. Error routes, such as a call that fails, are not ways out. They stay where they lead when the block moves.
*/

/**
 * Lists the codes of every state that travels together with a state, the state itself among them. An editor that
 * keeps states together gives a function of this shape to every function in this file.
 */
export type BlockMembers = (process: WorkingProcess, code: string) => string[];

const onItsOwn: BlockMembers = (_process, code) => [code];

// One onward route of a state, which may lead nowhere yet: the state it is written in, where in that state it sits,
// and the state it leads to.
type WayOut = { source: string; path: (string | number)[]; target: string | undefined };

// The states that move together, the one everything outside them leads to, and the one route that leaves them.
type Block = { members: Set<string>; first: string; exit: WayOut };

/**
 * Lists the onward routes of a state, including those that lead nowhere yet. A decision has one for each rule and
 * one for its default. An end has none. Error routes are left out.
 */
function onwardRoutes(code: string, state: WorkingState): WayOut[] {
	if (state.state_type === 'choice') {
		return [
			...state.rules.map((rule, index): WayOut => ({ source: code, path: ['rules', index, 'next'], target: rule.next })),
			{ source: code, path: ['default'], target: state.default }
		];
	}
	return hasNext(state) ? [{ source: code, path: ['next'], target: state.next }] : [];
}

/**
 * Finds the block a state moves in, or nothing when that block cannot move: it has more than one way out or none,
 * or something outside it leads to a state in it other than its way in.
 */
function blockOf(process: WorkingProcess, code: string, membersOf: BlockMembers): Block | undefined {
	if (!(code in process.states)) return undefined;
	const members = new Set(membersOf(process, code).filter((member) => member in process.states));

	const exits = [...members]
		.flatMap((member) => onwardRoutes(member, process.states[member]))
		.filter((route) => route.target === undefined || !members.has(route.target));
	if (exits.length !== 1) return undefined;

	// The way in is the state of the block the journey reaches first.
	const first = journeyOrder(process).find((each) => members.has(each));
	if (first === undefined) return undefined;

	// Moving would cut a route that enters the block anywhere but its way in, so such a block stays where it is.
	const entersElsewhere = Object.entries(process.states).some(
		([source, state]) => !members.has(source) && routesOf(state).some((route) => members.has(route.target) && route.target !== first)
	);
	const startsElsewhere = process.start !== undefined && members.has(process.start) && process.start !== first;
	return entersElsewhere || startsElsewhere ? undefined : { members, first, exit: exits[0] };
}

/**
 * Finds the block that a block would swap places with if it moved down, which is the block its way out leads to.
 * Returns nothing when there is no such block, so one check serves both the button and the move itself.
 */
function laterBlock(process: WorkingProcess, block: Block, membersOf: BlockMembers): Block | undefined {
	const target = block.exit.target;
	if (target === undefined) return undefined;

	// The way out must lead to the way in of a block that can move, made of other states than the block that is moving.
	const later = blockOf(process, target, membersOf);
	if (!later || later.first !== target || [...later.members].some((member) => block.members.has(member))) return undefined;

	// Two blocks that continue to each other have no order to change.
	return later.exit.target === block.first ? undefined : later;
}

/**
 * Finds the block that a block would swap places with if it moved up, which is the one block whose way out leads
 * to it. Returns nothing when no block or more than one does.
 */
function earlierBlock(process: WorkingProcess, block: Block, membersOf: BlockMembers): Block | undefined {
	const candidates = new Map<string, Block>();
	for (const { source } of routesInto(process, block.first)) {
		if (block.members.has(source)) continue;
		const earlier = blockOf(process, source, membersOf);
		if (earlier && laterBlock(process, earlier, membersOf)?.first === block.first) candidates.set(earlier.first, earlier);
	}
	return candidates.size === 1 ? [...candidates.values()][0] : undefined;
}

/**
 * Points one onward route of a state at a new state, or leaves it leading nowhere when there is none.
 */
function withWayOut(state: WorkingState, path: (string | number)[], target: string | undefined): WorkingState {
	if (target !== undefined) return withRouteTarget(state, path, target);
	if (state.state_type !== 'choice') return withoutNext(state);

	const ruleTargets = state.rules.map((rule, index) => (path[0] === 'rules' && path[1] === index ? nothingYet : (rule.next ?? nothingYet)));
	return withChoiceTargets(state, ruleTargets, path[0] === 'default' ? nothingYet : (state.default ?? nothingYet));
}

/**
 * Returns a copy of the process in which a block has swapped places with the block it continues to. Everything
 * outside the two that led to the first block now leads to the second, the second continues to the first, and the
 * first continues to where the second went.
 */
function swapBlocks(process: WorkingProcess, first: Block, second: Block): WorkingProcess {
	const secondTarget = second.exit.target;

	// Routes inside either block are left alone, so a loop inside a module still goes back to its own start.
	const states = Object.fromEntries(
		Object.entries(process.states).map(([code, state]) => {
			if (first.members.has(code) || second.members.has(code)) return [code, state];
			const redirected = routesOf(state)
				.filter((route) => route.target === first.first)
				.reduce((current, route) => withRouteTarget(current, route.path, second.first), state);
			return [code, redirected];
		})
	);
	const redirected: WorkingProcess = { ...process, start: process.start === first.first ? second.first : process.start, states };

	const secondFirst = replaceState(redirected, second.exit.source, withWayOut(redirected.states[second.exit.source], second.exit.path, first.first));
	return replaceState(secondFirst, first.exit.source, withWayOut(secondFirst.states[first.exit.source], first.exit.path, secondTarget));
}

/**
 * Tells whether a step can move down, so the panel only offers a button that will work.
 */
export function canMoveLater(process: WorkingProcess, code: string, membersOf: BlockMembers = onItsOwn): boolean {
	const block = blockOf(process, code, membersOf);
	return block !== undefined && laterBlock(process, block, membersOf) !== undefined;
}

/**
 * Tells whether a step can move up, so the panel only offers a button that will work.
 */
export function canMoveEarlier(process: WorkingProcess, code: string, membersOf: BlockMembers = onItsOwn): boolean {
	const block = blockOf(process, code, membersOf);
	return block !== undefined && earlierBlock(process, block, membersOf) !== undefined;
}

/**
 * Returns a copy of the process in which a step, with the states that travel with it, has swapped places with the
 * block after it. If there is nothing to swap with, the process is returned as it is.
 */
export function moveLater(process: WorkingProcess, code: string, membersOf: BlockMembers = onItsOwn): WorkingProcess {
	const block = blockOf(process, code, membersOf);
	const later = block && laterBlock(process, block, membersOf);
	return block && later ? swapBlocks(process, block, later) : process;
}

/**
 * Returns a copy of the process in which a step, with the states that travel with it, has swapped places with the
 * block before it. This is the earlier block moving down, so it uses the same swap. If there is nothing to swap
 * with, the process is returned as it is.
 */
export function moveEarlier(process: WorkingProcess, code: string, membersOf: BlockMembers = onItsOwn): WorkingProcess {
	const block = blockOf(process, code, membersOf);
	const earlier = block && earlierBlock(process, block, membersOf);
	return block && earlier ? swapBlocks(process, earlier, block) : process;
}
