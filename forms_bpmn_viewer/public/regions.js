import {BPMN_NS} from './metadata.js';
const DI='http://www.omg.org/spec/BPMN/20100524/DI';
const DC='http://www.omg.org/spec/DD/20100524/DC';
const DD='http://www.omg.org/spec/DD/20100524/DI';

// Only structurally inferred routing regions collapse by default. Repeat
// collections remain expanded so their loop behaviour is not hidden.
export function routingRegions(model) {
  return [...model.nodes.values()].filter(n=>n.type==='subProcess' &&
    n.decomposition?.reason?.includes('routing region'));
}
export function collapsedAncestors(id,model,collapsed) {
  const result=[],seen=new Set();let node=model.nodes.get(id);
  while(node?.parentId && !seen.has(node.parentId)) {
    seen.add(node.parentId);if(collapsed.has(node.parentId))result.push(node.parentId);
    node=model.nodes.get(node.parentId);
  }
  return result;
}
// A band can be removed only when no other visible sibling occupies it.
// This keeps parallel branches safe; a shared row may remain wider/taller.
export function compressionBands(groups,shapes) {
  return groups.filter(g=>g.height>110 && !shapes.some(s=>s.id!==g.id &&
    s.parentId===g.parentId && s.y<g.y+g.height && s.y+s.height>g.y))
    .map(g=>({start:g.y+110,end:g.y+g.height})).sort((a,b)=>a.start-b.start)
    .filter((b,i,all)=>!all.slice(0,i).some(a=>a.end>b.start));
}
export function compressY(y,bands) {
  return y-bands.reduce((sum,b)=>sum+Math.max(0,Math.min(y,b.end)-b.start),0);
}

// Build a display-only copy from the original XML on every toggle: coordinates
// never accumulate rounding/drift, and the process and downloaded XML stay intact.
export function regionView(xml,model,collapsed) {
  const doc=new DOMParser().parseFromString(xml,'application/xml');
  const shapes=[...doc.getElementsByTagNameNS(DI,'BPMNShape')];
  const boxes=shapes.map(shape=>{
    const b=shape.getElementsByTagNameNS(DC,'Bounds')[0],id=shape.getAttribute('bpmnElement');
    return {id,parentId:model.nodes.get(id)?.parentId,shape,b,x:+b.getAttribute('x'),y:+b.getAttribute('y'),width:+b.getAttribute('width'),height:+b.getAttribute('height')};
  });
  const active=boxes.filter(b=>collapsed.has(b.id) && !collapsedAncestors(b.id,model,collapsed).length);
  const hidden=id=>collapsedAncestors(id,model,collapsed).length>0;
  // Compression at process level cannot move an expanded enclosing subprocess.
  // Nested collapses still hide contents but retain their enclosing layout.
  const bands=compressionBands(active.filter(g=>model.nodes.get(g.parentId)?.type==='process'),boxes.filter(b=>!hidden(b.id)));
  for(const box of active) {
    box.shape.setAttribute('isExpanded','false');
    box.b.setAttribute('x',box.x+box.width/2-165);
    box.b.setAttribute('width','330');box.b.setAttribute('height','110');
    const element=[...doc.getElementsByTagNameNS(BPMN_NS,'subProcess')].find(e=>e.getAttribute('id')===box.id);
    element.setAttribute('name',(model.nodes.get(box.id)?.name || '').replace(/^Routing region\s*·\s*/,''));
  }
  for(const shape of shapes)if(hidden(shape.getAttribute('bpmnElement')))shape.remove();
  for(const edge of [...doc.getElementsByTagNameNS(DI,'BPMNEdge')]) {
    const id=edge.getAttribute('bpmnElement');if(hidden(id)){edge.remove();continue;}
    const flow=model.nodes.get(id),points=[...edge.getElementsByTagNameNS(DD,'waypoint')];
    const source=active.find(b=>b.id===flow?.source),target=active.find(b=>b.id===flow?.target);
    // Outgoing port is the new bottom, not the bottom of the expanded region.
    function port(box,index,y){
      const point=points.at(index),next=points.at(index===0 ? 1 : -2);
      if(!point)return;
      const oldX=+point.getAttribute('x'),oldY=+point.getAttribute('y'),x=box.x+box.width/2;
      if(next && +next.getAttribute('x')===oldX)next.setAttribute('x',x);
      if(next && +next.getAttribute('y')===oldY)next.setAttribute('y',y);
      point.setAttribute('x',x);point.setAttribute('y',y);
    }
    if(source)port(source,0,source.y+110);
    if(target)port(target,-1,target.y);
  }
  for(const tag of [[DC,'Bounds'],[DD,'waypoint']])for(const point of doc.getElementsByTagNameNS(...tag)) {
    point.setAttribute('y',compressY(+point.getAttribute('y'),bands));
  }
  return new XMLSerializer().serializeToString(doc);
}
