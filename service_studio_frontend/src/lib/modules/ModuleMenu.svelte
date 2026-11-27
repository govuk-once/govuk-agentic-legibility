<script lang="ts">
	import { tick } from 'svelte';
	import type { ModuleCategory, ModuleTile, PaletteTool } from '$lib/modules/module-catalogue';
	import ModuleIcon from '$lib/modules/ModuleIcon.svelte';

	/*
		The menu of modules that runs across the top of an editor. Each category has its name over a row of tiles, with a
		line between categories. A tile shows a tooltip with the module's name and what it does when it is pointed at or
		reached with the keyboard. A tile the editor can add is dragged onto the canvas. A tile it cannot add yet is shown
		so the menu is complete, but cannot be dragged.
	*/
	interface Props {
		categories: ModuleCategory[];
		// What the editor can add, each found by the key of its tile. A tile with no entry here cannot be dragged.
		tools: PaletteTool[];
	}

	let { categories, tools }: Props = $props();

	const toolFor = (key: string) => tools.find((tool) => tool.module === key);

	// The gap kept between the tooltip and its tile, and between the tooltip and the edge of the window.
	const gap = 10;

	// The module whose tooltip is showing and where it is drawn. Only one tooltip shows at a time, so there is one
	// tooltip element, moved to whichever tile is pointed at or has the focus. It is hidden until it has been placed.
	// It is always replaced whole, so it is kept raw and its module stays the same object as the tile's.
	let shown = $state.raw<{ module: ModuleTile; top: number; left: number; pointAt: number; placed: boolean }>();
	let tooltip = $state<HTMLElement>();

	/**
	 * Shows the tooltip of a tile below it. The tooltip is fixed to the window and moved back inside it when the tile
	 * is near an edge, so it can always be read. Its small point stays on the tile.
	 */
	async function showTooltip(module: ModuleTile, tile: HTMLElement) {
		shown = { module, top: 0, left: 0, pointAt: 0, placed: false };
		// The tooltip is measured once it holds the module's words, because its size depends on them.
		await tick();
		if (!tooltip || shown?.module !== module) return;
		const tileBox = tile.getBoundingClientRect();
		const { width } = tooltip.getBoundingClientRect();
		const centre = tileBox.left + tileBox.width / 2;
		const left = Math.min(Math.max(centre - width / 2, gap), window.innerWidth - width - gap);
		shown = { module, top: tileBox.bottom + gap, left, pointAt: centre - left, placed: true };
	}

	function hideTooltip() {
		shown = undefined;
	}

	/**
	 * Marks the drag as carrying what the tile adds, so the canvas only reacts to a drop that came from this menu and
	 * not to some other kind of drag the browser also fires this event for.
	 */
	function handleDragStart(event: DragEvent, tool: PaletteTool) {
		hideTooltip();
		event.dataTransfer?.setData('application/x-journey-node', tool.value);
		if (event.dataTransfer) event.dataTransfer.effectAllowed = 'copy';
	}
</script>

<nav class="module-menu" aria-label="Add to the journey">
	{#each categories as category, index (category.label)}
		{#if index > 0}
			<span class="module-menu__divider" aria-hidden="true"></span>
		{/if}
		<div class="module-menu__category">
			<p class="module-menu__category-label secondary-text" id="module-menu-category-{index}">{category.label}</p>
			<ul class="module-menu__tiles" aria-labelledby="module-menu-category-{index}">
				{#each category.modules as module (module.key)}
					{@const tool = toolFor(module.key)}
					<li>
						<div
							class="module-menu__tile"
							class:module-menu__tile--inactive={!tool}
							role="button"
							tabindex="0"
							draggable={tool ? 'true' : 'false'}
							aria-disabled={tool ? undefined : 'true'}
							aria-label={tool ? `${module.label}, drag onto the canvas to add` : `${module.label}, not available yet`}
							aria-describedby={shown?.module === module ? 'module-menu-tooltip' : undefined}
							onpointerenter={(event) => showTooltip(module, event.currentTarget)}
							onpointerleave={hideTooltip}
							onfocus={(event) => showTooltip(module, event.currentTarget)}
							onblur={hideTooltip}
							onkeydown={(event) => {
								if (event.key === 'Escape') hideTooltip();
							}}
							ondragstart={(event) => tool && handleDragStart(event, tool)}
						>
							<ModuleIcon name={module.key} />
						</div>
					</li>
				{/each}
			</ul>
		</div>
	{/each}
</nav>

{#if shown}
	<div
		bind:this={tooltip}
		class="module-menu__tooltip"
		id="module-menu-tooltip"
		role="tooltip"
		style:top="{shown.top}px"
		style:left="{shown.left}px"
		style:--point-at="{shown.pointAt}px"
		style:visibility={shown.placed ? 'visible' : 'hidden'}
	>
		<span class="module-menu__tooltip-name">{shown.module.label}</span>
		<span class="module-menu__tooltip-description">{shown.module.description}</span>
	</div>
{/if}

<style>
	/* The menu lines up with the page title above it, and wraps onto a second row on a narrow screen. */
	.module-menu {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		gap: 10px;
		padding: 10px 40px;
		background-color: #ffffff;
		border-bottom: 1px solid #b1b4b6;
		font-family: 'GDS Transport', arial, sans-serif;
	}

	.module-menu__divider {
		align-self: flex-end;
		width: 1px;
		height: 44px;
		background-color: #b1b4b6;
	}

	.module-menu__category {
		display: flex;
		flex-direction: column;
		gap: 5px;
	}

	/* The category names are written like the stage names in the progress banner above. */
	.module-menu__category-label {
		margin: 0;
		font-size: 1rem;
		line-height: 1.25;
	}

	.module-menu__tiles {
		display: flex;
		gap: 5px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	/* A grey square holding the module's icon. Pointing at it darkens the square, its edge and the icon. */
	.module-menu__tile {
		display: flex;
		align-items: center;
		justify-content: center;
		box-sizing: border-box;
		width: 44px;
		height: 44px;
		color: #3f484c;
		background-color: #f3f2f1;
		border: 1.5px solid transparent;
		cursor: grab;
	}

	.module-menu__tile:hover {
		color: #0b0c0c;
		background-color: #e1e3e4;
		border-color: #8a9094;
	}

	.module-menu__tile:focus-visible {
		outline: 3px solid #ffdd00;
		outline-offset: 0;
		box-shadow: inset 0 0 0 2px #0b0c0c;
	}

	/* A module that cannot be added yet looks the same, so the menu can be judged as designed, but cannot be grabbed. */
	.module-menu__tile--inactive {
		cursor: default;
	}

	/* The tooltip is fixed to the window above everything else. Its small point is placed over the tile it belongs to,
		which is where --point-at says, measured from the tooltip's edge. */
	.module-menu__tooltip {
		position: fixed;
		z-index: 20;
		display: flex;
		flex-direction: column;
		gap: 5px;
		width: 260px;
		padding: 10px 15px;
		color: #ffffff;
		background-color: #0b0c0c;
		pointer-events: none;
	}

	.module-menu__tooltip::before {
		content: '';
		position: absolute;
		top: -5px;
		left: calc(var(--point-at) - 6px);
		width: 12px;
		height: 12px;
		background-color: #0b0c0c;
		transform: rotate(45deg);
	}

	.module-menu__tooltip-name {
		font-size: 1rem;
		font-weight: 700;
		line-height: 1.25;
	}

	.module-menu__tooltip-description {
		font-size: 1rem;
		line-height: 1.25;
		color: #d8d8d3;
	}

	@media (max-width: 640px) {
		.module-menu {
			padding-inline: 15px;
		}
	}
</style>
