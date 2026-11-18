/*
	Reading and writing the ISO 8601 durations the schema uses, such as P7D for seven days or PT30S for thirty
	seconds. A page shows a duration as a number and a unit that a person can type, and writes it back the same way.
*/

// Matches a duration such as P14D or PT1H30M and captures the number for each unit, from years down to seconds.
export const durationPattern = /^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$/;

// The units a page offers for a duration, with how many seconds each one holds, from the largest down.
export const timeUnits = [
	{ unit: 'days', seconds: 86400 },
	{ unit: 'hours', seconds: 3600 },
	{ unit: 'minutes', seconds: 60 },
	{ unit: 'seconds', seconds: 1 }
] as const;

export type TimeUnit = (typeof timeUnits)[number]['unit'];

/**
 * Counts the seconds in a duration. Years and months are left out, because their length changes with the calendar,
 * so a duration that uses them, or text that is not a duration, gives nothing.
 */
export function durationInSeconds(duration: string): number | undefined {
	const match = durationPattern.exec(duration);
	if (!match || match[1] || match[2]) return undefined;
	const [weeks, days, hours, minutes, seconds] = match.slice(3).map((part) => Number(part ?? 0));
	return weeks * 604800 + days * 86400 + hours * 3600 + minutes * 60 + seconds;
}

/**
 * Writes a duration as a whole number of the largest unit it divides into exactly, so P7D is 7 days and PT90M is 90
 * minutes. A duration that cannot be read in seconds gives nothing.
 */
export function durationAsAmount(duration: string): { amount: number; unit: TimeUnit } | undefined {
	const total = durationInSeconds(duration);
	if (total === undefined) return undefined;
	const { unit, seconds } = timeUnits.find((each) => total % each.seconds === 0) ?? timeUnits[timeUnits.length - 1];
	return { amount: total / seconds, unit };
}

/**
 * Writes a number of one unit as a duration, so 7 days is P7D and 30 seconds is PT30S.
 */
export function durationFrom(amount: number, unit: TimeUnit): string {
	switch (unit) {
		case 'days':
			return `P${amount}D`;
		case 'hours':
			return `PT${amount}H`;
		case 'minutes':
			return `PT${amount}M`;
		case 'seconds':
			return `PT${amount}S`;
	}
}
