// Bounded, display-only nudges: keep labels near their original anchor and
// prefer clear space over boxes, other labels and orthogonal flow segments.
function overlap(a,b,pad=4) {
 return Math.max(0,Math.min(a.x+a.width+pad,b.x+b.width)-Math.max(a.x-pad,b.x))*Math.max(0,Math.min(a.y+a.height+pad,b.y+b.height)-Math.max(a.y-pad,b.y));
}
export function chooseLabelPosition(label,boxes,segments,occupied=[],target=null) {
 const anchor={x:label.x,y:label.y},candidates=[anchor];
 for(const dx of [0,-32,32,-64,64,-110,110,-180,180])for(const dy of [0,-24,24,-48,48,-80,80])candidates.push({x:anchor.x+dx,y:anchor.y+dy});
 if(target && !target.waypoints){
  candidates.push({x:target.x-label.width-12,y:target.y+(target.height-label.height)/2},
   {x:target.x+(target.width-label.width)/2,y:target.y-label.height-12},
   {x:target.x+(target.width-label.width)/2,y:target.y+target.height+12});
 }
 if(target?.waypoints)for(let i=1;i<target.waypoints.length;i++){
  const a=target.waypoints[i-1],b=target.waypoints[i];
  if(Math.abs(a.y-b.y)<1 && Math.abs(a.x-b.x)>=label.width+16)for(const dy of [-label.height-10,10])candidates.push({x:(a.x+b.x-label.width)/2,y:a.y+dy});
 }
 function score(p){
  const box={...label,...p};let result=Math.hypot(p.x-anchor.x,p.y-anchor.y)*.2;
  for(const obstacle of boxes)if(overlap(box,obstacle))result+=100000+overlap(box,obstacle)*10;
  for(const other of occupied)if(overlap(box,other))result+=50000+overlap(box,other)*10;
  for(const line of segments)if(overlap(box,line,2))result+=3000+overlap(box,line,2)*5;
  return result;
 }
 let best=anchor,cost=score(anchor);
 for(const candidate of candidates){
  if(candidate.x<4 || candidate.y<4 || Math.hypot(candidate.x-anchor.x,candidate.y-anchor.y)>300)continue;
  const value=score(candidate);if(value<cost){best=candidate;cost=value;}
 }
 return best;
}
export function nudgeLabels(viewer){
 const registry=viewer.get('elementRegistry'),factory=viewer.get('graphicsFactory'),all=registry.getAll().filter(e=>e.parent&&!e.hidden);
 const boxes=all.filter(e=>e.type!=='label'&&!e.waypoints&&[e.x,e.y,e.width,e.height].every(Number.isFinite) && (e.type!=='bpmn:SubProcess'||e.collapsed));
 const segments=all.flatMap(e=>e.waypoints?.slice(1).map((b,i)=>{const a=e.waypoints[i];return {x:Math.min(a.x,b.x)-1,y:Math.min(a.y,b.y)-1,width:Math.max(2,Math.abs(b.x-a.x)),height:Math.max(2,Math.abs(b.y-a.y))};}) || []);
 const occupied=[];
 for(const element of all.filter(e=>e.type==='label')){
  const position=chooseLabelPosition(element,boxes,segments,occupied,element.labelTarget);
  element.x=position.x;element.y=position.y;occupied.push({x:element.x,y:element.y,width:element.width,height:element.height});
  factory.update('shape',element,registry.getGraphics(element));
 }
}
