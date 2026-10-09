// Fit from diagram coordinates, without cached SVG getBBox/viewbox dimensions.
export function diagramBounds(elements) {
  const points=[];
  for (const e of elements) {
    if (e.hidden) continue;
    if (e.waypoints) points.push(...e.waypoints);
    else if ([e.x,e.y,e.width,e.height].every(Number.isFinite) && e.width>=0 && e.height>=0) points.push({x:e.x,y:e.y},{x:e.x+e.width,y:e.y+e.height});
  }
  const valid=points.filter(p=>Number.isFinite(p.x)&&Number.isFinite(p.y));
  if (!valid.length) return null;
  const xs=valid.map(p=>p.x), ys=valid.map(p=>p.y);
  return {x:Math.min(...xs),y:Math.min(...ys),width:Math.max(...xs)-Math.min(...xs),height:Math.max(...ys)-Math.min(...ys)};
}
export function fittedViewbox(bounds,size,padding=40,maxScale=1) {
  if (!bounds || ![bounds.x,bounds.y,bounds.width,bounds.height,size.width,size.height].every(Number.isFinite) || size.width<=0 || size.height<=0) return null;
  const scale=Math.min(maxScale,Math.max(1,size.width-padding*2)/Math.max(1,bounds.width),Math.max(1,size.height-padding*2)/Math.max(1,bounds.height));
  const width=size.width/scale,height=size.height/scale;
  return {x:bounds.x+bounds.width/2-width/2,y:bounds.y+bounds.height/2-height/2,width,height};
}
export function focusedViewbox(element,size,scale=1) {
  if (![element.x,element.y,element.width,element.height,size.width,size.height,scale].every(Number.isFinite) || size.width<=0 || size.height<=0 || scale<=0) return null;
  const width=size.width/scale,height=size.height/scale;
  return {x:element.x+element.width/2-width/2,y:element.y+element.height/2-height*.28,width,height};
}
