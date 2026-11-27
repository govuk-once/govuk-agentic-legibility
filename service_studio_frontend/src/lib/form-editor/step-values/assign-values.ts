import { expressionSchema, type Expression } from '$lib/schema/workflow/expression';
import { variablePathSchema } from '$lib/schema/workflow/primitives';
import type { WorkingAssign } from '$lib/schema/workflow/working-process';
import type { StepValueProblem, StepValuesResult } from '$lib/form-editor/step-values/step-values';

/*
	The values of an assign step. An assign sets one or more variables, and each is given a value of one kind: a fixed
	value, a copy of another variable, or one of the operations the schema offers. At the technical review the kind of
	each value is shown but cannot be changed, because a decision that reads the variable, or an input that saves
	into it, cannot be changed anywhere in Service Studio, so a new kind could break the journey with no way to put it
	right. Only the parts of the value can be changed.
*/

// The kinds of value an assign can set. Two pairs of operations are one kind each, because they take the same parts.
export type AssignKind = 'literal' | 'copy' | 'add' | 'date_offset' | 'now_plus' | 'append' | 'date_compare';

// The words a person sees for each kind of value. The record is keyed by every kind, so adding a kind without a label
// fails to compile.
export const assignKindLabels: Record<AssignKind, string> = {
	literal: 'Fixed value',
	copy: 'Copy',
	add: 'Add',
	date_offset: 'Date add or subtract',
	now_plus: 'Now plus',
	append: 'Append',
	date_compare: 'Date before or date difference'
};

/**
 * Tells which kind of value an expression is. A reference is a copy, an operation is named by its op, and anything
 * else is a fixed value.
 */
function assignKindOf(expression: Expression): AssignKind {
	if (expression === null || typeof expression !== 'object' || Array.isArray(expression)) return 'literal';
	if ('$' in expression) return 'copy';
	if (!('op' in expression)) return 'literal';
	switch (expression.op) {
		case 'add':
		case 'now_plus':
		case 'append':
			return expression.op;
		case 'date_add':
		case 'date_subtract':
			return 'date_offset';
		default:
			return 'date_compare';
	}
}

// The words for each part of a value, by the name the schema gives the part. A part without words here is shown by
// its schema name.
const partLabels: Record<string, string> = {
	$: 'Copy from',
	path: 'Path',
	value: 'Value',
	value_path: 'Value from'
};

/**
 * One part of a value as its panel shows it: the schema's name for the part, the words for it and its typed text.
 */
export interface AssignPart {
	name: string;
	label: string;
	text: string;
}

/**
 * One variable an assign sets, as its panel shows it.
 */
export interface AssignLine {
	variable: string;
	kind: AssignKind;
	parts: AssignPart[];
}

// The name a fixed value is typed under. A fixed value has no parts of its own, so it is typed as one whole value.
const wholeValue = 'value';

/**
 * Splits a value into the parts that are typed in its panel. A fixed value is typed whole, as JSON. A copy is typed
 * as the variable it copies. An operation has one part for each key except op, which is its kind and is kept as it
 * is, with text written as it is and anything else written as JSON.
 */
function partsOf(expression: Expression): AssignPart[] {
	const part = (name: string, text: string) => ({ name, label: partLabels[name] ?? name, text });
	if (assignKindOf(expression) === 'literal') return [part(wholeValue, JSON.stringify(expression))];
	return editableEntries(expression).map(([name, value]) => part(name, typeof value === 'string' ? value : JSON.stringify(value)));
}

// The keys of a copy or an operation that are typed in its panel, in the order they are written. The op key names
// the kind of value, which is not changed here, so it is left out.
function editableEntries(expression: Expression): [string, unknown][] {
	return Object.entries(expression as Record<string, unknown>).filter(([name]) => name !== 'op');
}

/**
 * Lists the variables an assign sets, each with the kind of value and its parts.
 */
export function assignLinesOf(state: WorkingAssign): AssignLine[] {
	return Object.entries(state.set).map(([variable, expression]) => ({
		variable,
		kind: assignKindOf(expression),
		parts: partsOf(expression)
	}));
}

// The id of each field of an assign's panel, which a problem names so the error summary can link to it.
export const assignVariableField = (line: number) => `assign-${line}-variable`;
export const assignPartField = (line: number, part: number) => `assign-${line}-part-${part}`;

/**
 * Turns the typed text of a part back into a value of the same type as it had before, so a number stays a number.
 * Text that should be JSON and is not gives nothing.
 */
function readPart(text: string, before: unknown): unknown {
	if (typeof before === 'string') return text;
	try {
		return JSON.parse(text);
	} catch {
		return undefined;
	}
}

/**
 * Reads the typed values into the assign. Each line keeps its kind of value. A variable name must be one the schema
 * accepts and be set only once, and each value must still match its kind.
 */
export function assignWithLines(
	state: WorkingAssign,
	typed: { variable: string; parts: string[] }[]
): StepValuesResult<WorkingAssign> {
	const problems: StepValueProblem[] = [];
	const set: Record<string, Expression> = {};
	const before = Object.values(state.set);

	typed.forEach((line, index) => {
		const variable = line.variable.trim();
		if (!variablePathSchema.safeParse(variable).success) {
			problems.push({ field: assignVariableField(index), message: 'Enter the variable to set as a name such as answers.step_3' });
		} else if (variable in set) {
			problems.push({ field: assignVariableField(index), message: `${variable} is set more than once` });
		}

		// A fixed value is read whole, as JSON.
		const old = before[index];
		if (assignKindOf(old) === 'literal') {
			const checked = expressionSchema.safeParse(readPart(line.parts[0], undefined));
			if (checked.success) set[variable] = checked.data;
			else problems.push({ field: assignPartField(index, 0), message: `Write the value of ${variable || 'this variable'} as JSON, such as "yes" or 3` });
			return;
		}

		// Any other kind is rebuilt part by part from the value it had before, and must still be the same kind.
		const read = editableEntries(old).map(([name, value], part) => [name, readPart(line.parts[part].trim(), value)] as const);
		const check = (parts: (readonly [string, unknown])[]) => {
			const checked = expressionSchema.safeParse({ ...(old as Record<string, unknown>), ...Object.fromEntries(parts) });
			return checked.success && assignKindOf(checked.data) === assignKindOf(old) ? checked.data : undefined;
		};
		const rebuilt = check(read);
		if (rebuilt !== undefined) {
			set[variable] = rebuilt;
			return;
		}
		// The problem is shown on the first part that fails when it is the only part changed.
		const partIndex = Math.max(0, read.findIndex((part) => check([part]) === undefined));
		problems.push({
			field: assignPartField(index, partIndex),
			message: `Check the ${partsOf(old)[partIndex].label.toLowerCase()} of ${variable || 'this variable'}`
		});
	});

	if (problems.length > 0) return { ok: false, problems };
	return { ok: true, state: { ...state, set } };
}
