<script lang="ts" module>
	/*
		The drawings of the module icons, copied from the icon sheet in the design. Each drawing is made of SVG shapes on
		a 24 by 24 grid. The line icons are drawn in the current text colour, so a tile can darken its icon on hover by
		changing its colour. The four basic shapes keep the colours the canvas gives the shapes they add.
	*/

	type Shape = ['path' | 'rect' | 'circle' | 'ellipse' | 'polygon', Record<string, string | number>];

	// A small dot inside a line icon is filled as well as outlined.
	const dot = { fill: 'currentColor' };

	const drawings = {
		// Not on the icon sheet: a page with a start arrow, drawn on the same grid and lines as the others.
		start_page: [
			['rect', { x: 4, y: 3, width: 16, height: 18, rx: 2 }],
			['path', { d: 'M8 7.5h8M8 11h8' }],
			['path', { d: 'M10.5 14.5v4l3.5-2z' }]
		],
		message: [
			['path', { d: 'M4 5.5h16v10H9.5L5 19.5v-4H4z' }],
			['path', { d: 'M8 9h8M8 12h5' }]
		],
		simple_question: [
			['rect', { x: 3, y: 7, width: 18, height: 10, rx: 2 }],
			['path', { d: 'M7.5 10.5v3M11.5 12h5' }]
		],
		formatted_question: [
			['rect', { x: 3, y: 7, width: 18, height: 10, rx: 2 }],
			['path', { d: 'M9.8 9.6l-.8 4.8M13.2 9.6l-.8 4.8M7.8 11h6.4M7.4 13h6.4' }],
			['path', { d: 'M17 10v4' }]
		],
		boolean_question: [
			['rect', { x: 3, y: 8, width: 18, height: 8, rx: 4 }],
			['circle', { cx: 16.5, cy: 12, r: 2 }]
		],
		select_one: [
			['circle', { cx: 6, cy: 6.5, r: 2.2 }],
			['circle', { cx: 6, cy: 12, r: 2.2 }],
			['circle', { cx: 6, cy: 12, r: 0.8, ...dot }],
			['circle', { cx: 6, cy: 17.5, r: 2.2 }],
			['path', { d: 'M11 6.5h9M11 12h9M11 17.5h9' }]
		],
		select_many: [
			['rect', { x: 3.5, y: 3.75, width: 4.5, height: 4.5, rx: 1 }],
			['path', { d: 'M4.5 6l1.1 1.1 1.8-2.2' }],
			['rect', { x: 3.5, y: 9.75, width: 4.5, height: 4.5, rx: 1 }],
			['rect', { x: 3.5, y: 15.75, width: 4.5, height: 4.5, rx: 1 }],
			['path', { d: 'M4.5 18l1.1 1.1 1.8-2.2' }],
			['path', { d: 'M11 6h9M11 12h9M11 18h9' }]
		],
		many_answers: [
			['rect', { x: 3, y: 2.5, width: 18, height: 5.5, rx: 1.5 }],
			['path', { d: 'M6.5 5.25h6' }],
			['path', { d: 'M5.5 8v13.5M5.5 12.5h3.5M5.5 17h3.5M5.5 21.5h3.5' }],
			['rect', { x: 9, y: 11, width: 12, height: 3, rx: 1.2 }],
			['rect', { x: 9, y: 15.5, width: 12, height: 3, rx: 1.2 }],
			['rect', { x: 9, y: 20, width: 12, height: 3, rx: 1.2 }]
		],
		data_question: [
			['ellipse', { cx: 10, cy: 6, rx: 6, ry: 2.5 }],
			['path', { d: 'M4 6v9c0 1.4 2.7 2.5 6 2.5' }],
			['path', { d: 'M4 10.5c0 1.4 2.7 2.5 6 2.5' }],
			['path', { d: 'M16 6v3' }],
			['circle', { cx: 17, cy: 17, r: 4.5 }],
			['path', { d: 'M15.6 15.6a1.5 1.5 0 1 1 2 1.4c-.4.2-.6.5-.6.9' }],
			['circle', { cx: 17, cy: 19.7, r: 0.5, ...dot }]
		],
		choice_decision: [
			['path', { d: 'M3 12h6' }],
			['path', { d: 'M9 12c3 0 3-6 7-6' }],
			['path', { d: 'M9 12h7' }],
			['path', { d: 'M9 12c3 0 3 6 7 6' }],
			['circle', { cx: 18.5, cy: 6, r: 1.6 }],
			['circle', { cx: 18.5, cy: 12, r: 1.6 }],
			['circle', { cx: 18.5, cy: 18, r: 1.6 }]
		],
		boolean_decision: [
			['path', { d: 'M3 12.5l3 3 5-6.5' }],
			['path', { d: 'M14.5 8l6 8M20.5 8l-6 8' }]
		],
		data_decision: [
			['ellipse', { cx: 8, cy: 6, rx: 5, ry: 2.2 }],
			['path', { d: 'M3 6v9c0 1.2 2.2 2.2 5 2.2' }],
			['path', { d: 'M3 10.5c0 1.2 2.2 2.2 5 2.2' }],
			['path', { d: 'M13 14h3' }],
			['path', { d: 'M16 14c1.5 0 1.5-4 3.5-4' }],
			['path', { d: 'M16 14c1.5 0 1.5 4 3.5 4' }],
			['circle', { cx: 21, cy: 10, r: 1.3 }],
			['circle', { cx: 21, cy: 18, r: 1.3 }]
		],
		deadline: [
			['rect', { x: 4, y: 5, width: 16, height: 15, rx: 2 }],
			['path', { d: 'M4 10h16M8 3v4M16 3v4' }],
			['circle', { cx: 15, cy: 15, r: 1.6, ...dot }]
		],
		wait: [
			['path', { d: 'M7 4h10M7 20h10' }],
			['path', { d: 'M8 4v3l4 5 4-5V4' }],
			['path', { d: 'M8 20v-3l4-5 4 5v3' }]
		],
		user_details: [
			['circle', { cx: 12, cy: 7.5, r: 3.5 }],
			['path', { d: 'M5 20c0-4 3-6.5 7-6.5s7 2.5 7 6.5' }]
		],
		submit: [
			['path', { d: 'M12 16V5M7.5 9.5L12 5l4.5 4.5' }],
			['path', { d: 'M5 14v5h14v-5' }]
		],
		payment: [
			['rect', { x: 3, y: 6, width: 18, height: 12, rx: 2 }],
			['path', { d: 'M3 10h18M6 15h4' }]
		],
		information: [
			['circle', { cx: 12, cy: 12, r: 9 }],
			['path', { d: 'M12 11v6' }],
			['circle', { cx: 12, cy: 7.6, r: 0.9, ...dot }]
		],
		phone_call: [['path', { d: 'M6 4h3l1.5 4-2 1.5a11 11 0 0 0 6 6L16 13.5l4 1.5v3a2 2 0 0 1-2 2A15 15 0 0 1 4 6a2 2 0 0 1 2-2z' }]],
		letter: [
			['rect', { x: 3, y: 6, width: 18, height: 13, rx: 2 }],
			['path', { d: 'M3 8l9 6 9-6' }]
		],
		// The basic shapes look like what they add to the canvas, in the canvas colours.
		start: [['circle', { cx: 12, cy: 12, r: 8, fill: '#0b0c0c', stroke: 'none' }]],
		input: [['rect', { x: 1.75, y: 6.75, width: 20.5, height: 10.5, rx: 2, fill: '#ffffff', stroke: '#1d70b8', 'stroke-width': 1.5 }]],
		output: [['rect', { x: 1.75, y: 6.75, width: 20.5, height: 10.5, rx: 2, fill: '#ffffff', stroke: '#4c2c92', 'stroke-width': 1.5 }]],
		decision: [['polygon', { points: '12,1.5 22.5,12 12,22.5 1.5,12', fill: '#ffdd00', stroke: 'none' }]],
		end: [['circle', { cx: 12, cy: 12, r: 7, fill: '#00703c', stroke: '#0b0c0c', 'stroke-width': 2 }]]
	} satisfies Record<string, Shape[]>;

	export type ModuleIconName = keyof typeof drawings;
</script>

<script lang="ts">
	interface Props {
		name: ModuleIconName;
		// The width and height the icon is drawn at, in pixels. The menu uses 22.
		size?: number;
	}

	let { name, size = 22 }: Props = $props();
</script>

<!-- The icon is decoration beside a label that says what it is, so screen readers skip it. -->
<svg
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width="1.7"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
	focusable="false"
>
	{#each drawings[name] as [tag, attributes], index (index)}
		<svelte:element this={tag} {...attributes} />
	{/each}
</svg>
