export function preferredFontSize(value) {const number=Number(value);return Number.isFinite(number)&&number>=12&&number<=24 ? Math.round(number) : 18;}

// Reuse bpmn-js's text layout/renderer, rewrapping full labels at each size.
// Reduce individual labels if needed; changing CSS alone would retain old wraps.
export function resizeLabels(viewer,requestedSize) {
 const registry=viewer.get('elementRegistry'),renderer=viewer.get('textRenderer'),factory=viewer.get('graphicsFactory'),style=renderer.getDefaultStyle();
 const base=preferredFontSize(requestedSize);
 for(const element of registry.getAll()) {
  if (!element.parent || element.waypoints || element.hidden || element.type==='label' || !Number.isFinite(element.width)) continue;
  const gfx=registry.getGraphics(element),textStyle=style;
  // External route/event labels retain their existing compact size so they
  // do not collide with nearby routes. The control changes embedded task text.
  let size=base;
  for(;size>=1;size--) {
   textStyle.fontSize=size;factory.update('shape',element,gfx);
   const text=gfx.querySelector('.djs-label');if (!text)break;
   const box=text.getBBox();
   if (box.x>=5 && box.x+box.width<=element.width-5 && box.y>=5 && box.y+box.height<=element.height-5) break;
  }
 }
 style.fontSize=base;
}
