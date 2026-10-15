import {nudgeLabels} from './label-placement.js';
export function preferredFontSize(value) {const number=Number(value);return Number.isFinite(number)&&number>=12&&number<=24 ? Math.round(number) : 18;}

// Reuse bpmn-js's text layout/renderer, rewrapping full labels at each size.
// Reduce individual labels if needed; changing CSS alone would retain old wraps.
export function resizeLabels(viewer,requestedSize) {
 const registry=viewer.get('elementRegistry'),renderer=viewer.get('textRenderer'),factory=viewer.get('graphicsFactory'),style=renderer.getDefaultStyle(),external=renderer.getExternalStyle();
 const base=preferredFontSize(requestedSize);
 for(const element of registry.getAll()) {
  if (!element.parent || element.waypoints || element.hidden || !Number.isFinite(element.width)) continue;
  const gfx=registry.getGraphics(element);
  if (element.type==='label') {
   // Reflow external names without shrinking them back to their old 11px box.
   // Keep the original centre/top anchor; never grow cumulatively on changes.
   element._formsLabelBounds ||= {x:element.x,y:element.y,width:element.width,height:element.height};
   const anchor=element._formsLabelBounds;
   const name=element.businessObject.name || '';
   external.fontSize=base;
   const unwrapped=renderer.getDimensions(name,{box:{width:100000},style:external});
   const target=element.labelTarget;
   const horizontal=target?.waypoints?.slice(1).map((p,i)=>Math.abs(p.y-target.waypoints[i].y)<1 ? Math.abs(p.x-target.waypoints[i].x) : 0) || [];
   const maxWidth=horizontal.some(w=>w>0) ? Math.max(90,Math.min(310,Math.max(...horizontal)-30)) : 310;
   element.width=Math.max(anchor.width,Math.min(maxWidth,Math.max(90,Math.ceil(unwrapped.width)+16)));
   const dimensions=renderer.getDimensions(name,{box:{width:element.width},style:external});
   element.height=Math.max(anchor.height,Math.ceil(dimensions.height)+6);
   element.x=anchor.x+anchor.width/2-element.width/2;element.y=anchor.y;
   if (target?.type.endsWith('Gateway') || target?.type.endsWith('Event')) {
    element.x=target.x+target.width+12;element.y=target.y+(target.height-element.height)/2;
   } else if (target?.waypoints?.every(p=>Math.abs(p.x-target.waypoints[0].x)<1)) {
    element.x=anchor.x;
   }
   factory.update('shape',element,gfx);
   continue;
  }
  const textStyle=style;
  let size=base;
  for(;size>=1;size--) {
   textStyle.fontSize=size;factory.update('shape',element,gfx);
   const text=gfx.querySelector('.djs-label');if (!text)break;
   const box=text.getBBox();
   if (box.x>=5 && box.x+box.width<=element.width-5 && box.y>=5 && box.y+box.height<=element.height-5) break;
  }
 }
 style.fontSize=base;external.fontSize=base;
 nudgeLabels(viewer);
}
