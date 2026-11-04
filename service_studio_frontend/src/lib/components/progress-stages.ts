// The five stages shown in the banner while a service is edited. Both editor pages are on the third
// stage, so the list is kept in one place instead of being written out again on each page.
export const editStages = [
	{ number: 1, label: 'Start', state: 'complete' as const },
	{ number: 2, label: 'Create', state: 'complete' as const },
	{ number: 3, label: 'Edit and review', state: 'current' as const },
	{ number: 4, label: 'Policy check', state: 'upcoming' as const },
	{ number: 5, label: 'Publish', state: 'upcoming' as const }
];
