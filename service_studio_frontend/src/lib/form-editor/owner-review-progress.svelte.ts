/*
	How far the owner review has got, shared by its pages so a step can show what an earlier one did. It lasts while
	the browser tab stays on Service Studio, and is not saved with the form, because it is about the review and not
	about the form.
*/
export const ownerReviewProgress = $state({
	// Shows example problems in place of the real checks, which come from the tech review once it is built. It is only
	// for seeing the design with problems, and is switched on and off on the Review page.
	showExampleProblems: false
});
