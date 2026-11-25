/*
	A design setting shared by the owner review pages. It lasts while the browser tab stays on Service Studio, and is
	not saved with the draft, because it is only for seeing the design. How far the owner review has got is saved with
	the draft instead.
*/
export const ownerReviewProgress = $state({
	// Shows example problems in place of the real checks, which come from the tech review once it is built. It is only
	// for seeing the design with problems, and is switched on and off on the Review page.
	showExampleProblems: false
});
