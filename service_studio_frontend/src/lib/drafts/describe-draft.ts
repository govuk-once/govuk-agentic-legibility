import type { DraftStage } from './draft-store';

/*
	The words the list of drafts uses for each draft: how long ago it was edited, and a tag for the stage it was left at.
*/

// The tag shown for each stage, with its GOV.UK tag colour.
export const draftStageTags: Record<DraftStage, { label: string; colour: string }> = {
	Edit: { label: 'Draft', colour: 'grey' },
	'Owner review': { label: 'In owner review', colour: 'yellow' },
	'Tech review': { label: 'In tech review', colour: 'light-blue' }
};

// Each unit of time with how many seconds it holds, largest first, so a time is given in the largest unit it fills.
const units: [Intl.RelativeTimeFormatUnit, number][] = [
	['year', 365 * 24 * 60 * 60],
	['month', 30 * 24 * 60 * 60],
	['week', 7 * 24 * 60 * 60],
	['day', 24 * 60 * 60],
	['hour', 60 * 60],
	['minute', 60]
];

// Writes "yesterday" and "last week" in place of "1 day ago" and "1 week ago".
const relativeTime = new Intl.RelativeTimeFormat('en-GB', { numeric: 'auto' });

/**
 * Says how long ago a draft was edited, such as "edited 2 hours ago" or "edited yesterday". A draft saved less than a
 * minute ago, or with a clock that is ahead, was edited "just now".
 */
export function editedAgo(savedAt: string, now: Date): string {
	const seconds = (now.getTime() - new Date(savedAt).getTime()) / 1000;
	const unit = units.find(([, size]) => seconds >= size);
	if (!unit) return 'edited just now';

	const [name, size] = unit;
	return `edited ${relativeTime.format(-Math.floor(seconds / size), name)}`;
}
