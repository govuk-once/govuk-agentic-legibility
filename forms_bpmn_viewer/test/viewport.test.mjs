import {test} from 'node:test';
import assert from 'node:assert/strict';
import {diagramBounds,fittedViewbox,focusedViewbox} from '../public/viewport.js';
import {formFeatures,matchesFilters} from '../public/metadata.js';

test('fit includes negative coordinates, connections and labels, excludes roots/hidden elements',()=>{
 const bounds=diagramBounds([{id:'root'},{x:0,y:10,width:100,height:80},{waypoints:[{x:-30,y:20},{x:200,y:40}]},{x:170,y:80,width:80,height:30},{hidden:true,x:-1000,y:0,width:10,height:10}]);
 assert.deepEqual(bounds,{x:-30,y:10,width:280,height:100});
 const box=fittedViewbox(bounds,{width:800,height:600});
 assert.ok(Object.values(box).every(Number.isFinite));
 assert.ok(box.x<=bounds.x && box.y<=bounds.y);assert.ok(box.x+box.width>=250 && box.y+box.height>=110);
});
test('fit stays finite for empty, point, long and invalid diagram bounds',()=>{
 assert.equal(diagramBounds([{id:'root'}]),null);assert.equal(fittedViewbox(null,{width:800,height:600}),null);
 assert.equal(fittedViewbox({x:0,y:0,width:100,height:100},{width:0,height:0}),null);
 assert.equal(fittedViewbox({x:NaN,y:0,width:100,height:100},{width:800,height:600}),null);
 for (const height of [0,3000,1000000]) assert.ok(Object.values(fittedViewbox({x:10,y:-50,width:100,height},{width:800,height:600})).every(Number.isFinite));
});
test('readable view is independent of previous SVG transform or zoom',()=>{
 const element={x:400,y:1000,width:330,height:90},size={width:800,height:600};
 const box=focusedViewbox(element,size);assert.equal(box.width,800);assert.equal(box.height,600);assert.equal(box.x,165);assert.equal(box.y,877);
 assert.equal(focusedViewbox({...element,x:Infinity},size),null);
});
test('source features distinguish routing, repeats, exits and compiled answer kinds',()=>{
 const metadata={source_export:{content:{steps:[{data:{answer_type:'selection',is_repeatable:true,is_optional:true},routing_conditions:[{}],exit_pages:[{}]}]}},questions:{q:{schema:{kind:'select_many'}},repeat_control:{generated:true,schema:{kind:'boolean'}}}};
 const result=formFeatures(metadata,{decomposition:[{}]});
 assert.deepEqual(result.features,['repeatable','routing','exits','optional','grouped']);assert.deepEqual(result.answerTypes,['selection']);assert.deepEqual(result.compiledKinds,['select_many']);
 const form={...result,name:'A form',formId:'1',folder:'1',issues:[]};
 assert.ok(matchesFilters(form,{feature:'routing',answerType:'selection',compiledKind:'select_many'}));
 assert.ok(!matchesFilters(form,{feature:'linear'}));assert.ok(!matchesFilters(form,{issuesOnly:true}));
});
test('unknown metadata is not classified as a linear form',()=>{
 assert.deepEqual(formFeatures(null,null).features,['unknown']);
 assert.deepEqual(formFeatures({source_export:{content:{steps:[{data:{answer_type:'text'}}]}}},null).features,['linear']);
});
