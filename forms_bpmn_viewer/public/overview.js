import {diagramBounds,fittedViewbox} from './viewport.js';
const NS='http://www.w3.org/2000/svg';
function svg(tag,attrs) { const e=document.createElementNS(NS,tag);for(const [key,value] of Object.entries(attrs)) e.setAttribute(key,value);return e; }
export function createOverview(viewer,element) {
  const drawing=svg('svg',{'aria-label':'Whole journey overview',role:'region',tabindex:0}),shapes=svg('g',{}),marker=svg('rect',{class:'overview-viewport',fill:'#2461a526',stroke:'#2461a5','stroke-width':2,'vector-effect':'non-scaling-stroke'});
  drawing.append(shapes,marker);element.append(drawing);
  let bounds=null,dragging=false;
  function updateViewport() {
    if (!bounds) return;
    const box=viewer.get('canvas').viewbox(false);
    if (![box.x,box.y,box.width,box.height].every(Number.isFinite)) return;
    for(const key of ['x','y','width','height']) marker.setAttribute(key,box[key]);
  }
  function resize() {
    if (!bounds) return;
    const box=fittedViewbox(bounds,{width:drawing.clientWidth,height:drawing.clientHeight},10,Infinity);
    if (box) drawing.setAttribute('viewBox',`${box.x} ${box.y} ${box.width} ${box.height}`);
    updateViewport();
  }
  function rebuild() {
    shapes.replaceChildren();const elements=viewer.get('elementRegistry').getAll();bounds=diagramBounds(elements);element.hidden=!bounds;
    if (!bounds) return;
    // Structural thumbnail only: no text, task icons or editable elements.
    for (const e of elements) {
      if (e.hidden || !e.parent || e.type==='label') continue;
      let shape;
      if (e.waypoints) shape=svg('polyline',{points:e.waypoints.map(p=>`${p.x},${p.y}`).join(' '),fill:'none'});
      else if (![e.x,e.y,e.width,e.height].every(Number.isFinite)) continue;
      else if (e.type.endsWith('Gateway')) shape=svg('polygon',{points:`${e.x+e.width/2},${e.y} ${e.x+e.width},${e.y+e.height/2} ${e.x+e.width/2},${e.y+e.height} ${e.x},${e.y+e.height/2}`});
      else if (e.type.endsWith('Event')) shape=svg('ellipse',{cx:e.x+e.width/2,cy:e.y+e.height/2,rx:e.width/2,ry:e.height/2});
      else shape=svg('rect',{x:e.x,y:e.y,width:e.width,height:e.height,rx:8});
      shape.setAttribute('class',e.type==='bpmn:SubProcess' ? 'overview-group'+(e.collapsed ? ' overview-group-collapsed' : '') : 'overview-element');shapes.append(shape);
    }
    resize();
  }
  function navigate(event) {
    if (!bounds) return;
    const matrix=drawing.getScreenCTM();if (!matrix) return;
    const point=new DOMPoint(event.clientX,event.clientY).matrixTransform(matrix.inverse()),canvas=viewer.get('canvas'),box=canvas.viewbox(false);
    if (![point.x,point.y,box.width,box.height].every(Number.isFinite)) return;
    canvas.viewbox({x:point.x-box.width/2,y:point.y-box.height/2,width:box.width,height:box.height});
  }
  drawing.addEventListener('pointerdown',event=>{if(event.button!==0 || !bounds)return;dragging=true;drawing.setPointerCapture(event.pointerId);navigate(event);event.preventDefault();});
  drawing.addEventListener('pointermove',event=>{if(dragging)navigate(event);});
  for(const name of ['pointerup','pointercancel','lostpointercapture']) drawing.addEventListener(name,()=>{dragging=false;});
  drawing.addEventListener('keydown',event=>{
    if (!bounds || !['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
    event.preventDefault();const canvas=viewer.get('canvas'),box=canvas.viewbox(false);
    const next={x:box.x,y:box.y,width:box.width,height:box.height};
    if(event.key==='ArrowUp')next.y-=box.height*.25;if(event.key==='ArrowDown')next.y+=box.height*.25;
    if(event.key==='ArrowLeft')next.x-=box.width*.25;if(event.key==='ArrowRight')next.x+=box.width*.25;
    if(event.key==='Home')next.y=bounds.y;if(event.key==='End')next.y=bounds.y+bounds.height-box.height;
    canvas.viewbox(next);
  });
  viewer.on('canvas.viewbox.changed',updateViewport);
  new ResizeObserver(resize).observe(drawing);
  return {rebuild,clear(){bounds=null;shapes.replaceChildren();element.hidden=true;}};
}
