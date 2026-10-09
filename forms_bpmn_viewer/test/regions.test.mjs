import {test} from 'node:test';
import assert from 'node:assert/strict';
import {routingRegions,collapsedAncestors,compressionBands,compressY} from '../public/regions.js';
test('only inferred routing regions collapse, not repeat collections or arbitrary subprocesses',()=>{
 const model={nodes:new Map([['a',{id:'a',type:'subProcess',decomposition:{reason:'acyclic single-entry/single-continuation routing region'}}],['b',{id:'b',type:'subProcess',decomposition:{reason:'repeat collection'}}],['c',{id:'c',type:'subProcess'}]])};
 assert.deepEqual(routingRegions(model).map(n=>n.id),['a']);
});
test('navigation reveals all collapsed ancestors in nested scopes',()=>{
 const model={nodes:new Map([['q',{parentId:'inner'}],['inner',{parentId:'outer'}],['outer',{parentId:'process'}]])};
 assert.deepEqual(collapsedAncestors('q',model,new Set(['inner','outer'])),['inner','outer']);
 assert.deepEqual(collapsedAncestors('unknown',model,new Set(['outer'])),[]);
});
test('multiple disjoint regions shorten the journey without shifting preceding nodes',()=>{
 const a={id:'a',parentId:'p',y:200,height:1200},b={id:'b',parentId:'p',y:1800,height:900};
 const bands=compressionBands([a,b],[a,b,{id:'next',parentId:'p',y:2900,height:90}]);
 assert.equal(compressY(100,bands),100);assert.equal(compressY(1400,bands),310);
 assert.equal(compressY(2900,bands),1020);assert.equal(compressY(200,bands),200);
});
test('parallel sibling rows are never squeezed into a collapsed region',()=>{
 const a={id:'a',parentId:'p',y:200,height:1200};
 assert.deepEqual(compressionBands([a],[a,{id:'branch',parentId:'p',y:400,height:90}]),[]);
});
