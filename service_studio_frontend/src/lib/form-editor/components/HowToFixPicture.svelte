<script lang="ts">
	import type { FixPicture, FixShape } from '../fix-pictures';

	/*
		Draws one before and after picture from fix-pictures.ts as a small SVG: the two shapes of the journey as it is
		in red, joined by a dashed line, an arrow, and the two shapes once fixed in green, joined by a dotted line.
	*/

	interface Props {
		picture: FixPicture;
	}

	let { picture }: Props = $props();

	const red = '#d4351c';
	const green = '#00703c';

	// The height of the picture, the middle line every shape is centred on, and the room between its parts.
	const height = 18;
	const middle = height / 2;
	const gap = 5;
	const lineLength = 16;
	const arrowLength = 20;

	// The width each shape takes up.
	const widths: Record<FixShape['shape'], number> = { step: 26, decision: 16, dot: 14 };

	// Where each part of one half of the picture starts, from the left, and where the half ends.
	function layoutHalf(start: number, [first, second]: [FixShape, FixShape]) {
		const lineStart = start + widths[first.shape] + gap;
		const secondStart = lineStart + lineLength + gap;
		return { first: start, lineStart, second: secondStart, end: secondStart + widths[second.shape] };
	}

	const before = $derived(layoutHalf(0, picture.before));
	const arrowStart = $derived(before.end + gap * 2);
	const after = $derived(layoutHalf(arrowStart + arrowLength + gap * 2, picture.after));

	// How a shape's outline and fill are drawn in a colour.
	function paint(shape: FixShape, colour: string) {
		return {
			stroke: shape.outline === 'none' ? 'none' : colour,
			'stroke-width': 1.5,
			'stroke-dasharray': shape.outline === 'dashed' ? '3 2' : undefined,
			fill: shape.fill === 'none' ? 'none' : colour,
			'fill-opacity': shape.fill === 'faint' ? 0.4 : undefined
		};
	}
</script>

<!-- One shape, drawn from its left edge and centred on the middle line. -->
{#snippet drawShape(shape: FixShape, left: number, colour: string)}
	{#if shape.shape === 'step'}
		<rect x={left + 0.75} y={middle - 7} width={widths.step - 1.5} height="14" {...paint(shape, colour)} />
	{:else if shape.shape === 'decision'}
		{@const centre = left + widths.decision / 2}
		<polygon points="{centre},{middle - 7.5} {centre + 7.5},{middle} {centre},{middle + 7.5} {centre - 7.5},{middle}" {...paint(shape, colour)} />
	{:else}
		<circle cx={left + widths.dot / 2} cy={middle} r="6.25" {...paint(shape, colour)} />
	{/if}
{/snippet}

<svg class="how-to-fix-picture" width={after.end} {height} viewBox="0 0 {after.end} {height}" role="img" aria-label={picture.description}>
	{@render drawShape(picture.before[0], before.first, red)}
	<line x1={before.lineStart} y1={middle} x2={before.lineStart + lineLength} y2={middle} stroke={red} stroke-width="2" stroke-dasharray="4 2" />
	{@render drawShape(picture.before[1], before.second, red)}

	<line x1={arrowStart} y1={middle} x2={arrowStart + arrowLength} y2={middle} stroke="#505a5f" stroke-width="1.5" />
	<polyline points="{arrowStart + arrowLength - 4},{middle - 4} {arrowStart + arrowLength},{middle} {arrowStart + arrowLength - 4},{middle + 4}" fill="none" stroke="#505a5f" stroke-width="1.5" />

	{@render drawShape(picture.after[0], after.first, green)}
	<line x1={after.lineStart} y1={middle} x2={after.lineStart + lineLength} y2={middle} stroke={green} stroke-width="2" stroke-linecap="round" stroke-dasharray="0 4" />
	{@render drawShape(picture.after[1], after.second, green)}
</svg>

<style>
	.how-to-fix-picture {
		display: block;
		overflow: visible;
	}
</style>
