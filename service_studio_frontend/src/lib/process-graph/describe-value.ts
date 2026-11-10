import type { Condition } from '$lib/schema/workflow/condition';
import type { Expression } from '$lib/schema/workflow/expression';

/*
	Plain sentences for the values the panel shows: a duration, a condition and an expression. Variable
	names are shown as they are written in the schema, because those are the names the executor team
	use, and only the words around them are plain English.
*/

// The words for each unit of an ISO 8601 duration, in the order the units are written.
const durationUnits = [
	['years', 'year'],
	['months', 'month'],
	['weeks', 'week'],
	['days', 'day'],
	['hours', 'hour'],
	['minutes', 'minute'],
	['seconds', 'second']
] as const;

// Matches a duration such as P14D or PT1H30M and captures each number, so it can be written in words.
const durationPattern = /^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$/;

/**
 * Writes a duration in words, so PT5S becomes "5 seconds" and P1DT12H becomes "1 day and 12 hours".
 * A duration held in a variable is described by the variable's name. Text that is not a duration is
 * returned as it is, so the panel never hides a value it cannot read.
 */
export function describeDuration(duration: string | { $: string }): string {
	if (typeof duration !== 'string') return `the time held in ${duration.$}`;

	const match = durationPattern.exec(duration);
	if (!match) return duration;

	const parts = durationUnits.flatMap(([plural, singular], index) => {
		const amount = match[index + 1];
		return amount === undefined ? [] : [`${amount} ${Number(amount) === 1 ? singular : plural}`];
	});

	return parts.length > 0 ? parts.join(' and ') : duration;
}

// Writes a literal operand the way it is written in the file, so text has quotes and numbers do not.
function describeLiteral(value: unknown): string {
	return JSON.stringify(value);
}

// The special path __now__ means the current time, so it is written as that.
function describePath(path: string): string {
	return path === '__now__' ? 'now' : path;
}

// The words between the path and the operand for each operator that compares the two.
const comparisonWords = {
	eq: 'is',
	lt: 'is less than',
	lte: 'is at most',
	gt: 'is more than',
	gte: 'is at least',
	contains: 'contains',
	date_before: 'is before',
	date_diff_greater_than: 'is greater than'
} as const;

/**
 * Writes a condition as one sentence, such as `upload_attempts is at least 3`. A condition made of
 * several parts is joined with and or or, and any part that is itself a group is put in brackets so
 * the order is clear.
 */
export function describeCondition(condition: Condition): string {
	switch (condition.op) {
		case 'is_true':
			return `${describePath(condition.path)} is true`;
		case 'is_false':
			return `${describePath(condition.path)} is false`;
		case 'not_empty':
			return `${describePath(condition.path)} has a value`;
		case 'before_now':
			return `${describePath(condition.path)} is before now`;
		case 'and':
		case 'or':
			return condition.all.map((part) => describeGroupMember(part)).join(` ${condition.op} `);
		case 'not':
			return `not (${condition.all.map((part) => describeCondition(part)).join(', ')})`;
		default: {
			// What remains compares the path with a value written in the file or held in another variable.
			const operand =
				condition.value_path !== undefined ? describePath(condition.value_path) : describeLiteral(condition.value);
			return `${describePath(condition.path)} ${comparisonWords[condition.op]} ${operand}`;
		}
	}
}

// A part of an and or an or is put in brackets when it is a group of its own.
function describeGroupMember(condition: Condition): string {
	const text = describeCondition(condition);
	return condition.op === 'and' || condition.op === 'or' ? `(${text})` : text;
}

/**
 * Writes an expression in words. A reference is shown as the variable name, a sum or a date offset as
 * the variable plus or minus the amount, and a value written in the file as it is written there.
 */
export function describeExpression(expression: Expression): string {
	if (expression === null || typeof expression !== 'object') return describeLiteral(expression);
	if (Array.isArray(expression)) return `[${expression.map((item) => describeExpression(item)).join(', ')}]`;

	// The schema has already checked these shapes, so the casts only tell the compiler which one it is.
	if ('$' in expression) return (expression as { $: string }).$;

	if ('op' in expression) {
		const operation = expression as Extract<Expression, { op: string }>;
		switch (operation.op) {
			case 'add':
			case 'date_add':
				return `${operation.path} plus ${operation.value}`;
			case 'date_subtract':
				return `${operation.path} minus ${operation.value}`;
			case 'now_plus':
				return `now plus ${operation.value_path}`;
			default:
				return describeCondition(operation);
		}
	}

	const entries = Object.entries(expression).map(([key, value]) => `${key}: ${describeExpression(value)}`);
	return `{ ${entries.join(', ')} }`;
}
