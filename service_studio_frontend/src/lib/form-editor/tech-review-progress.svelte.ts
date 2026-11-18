/*
	How far the technical review has got, shared by its pages. It lasts while the browser tab stays on Service Studio,
	and is not saved with the form, because it is about the review and not about the form. When the review is sent,
	the time it was checked is written into each developer step instead.
*/
export const techReviewProgress = $state({
	// The codes of the developer steps marked as checked on the step values page.
	checkedSteps: [] as string[]
});
