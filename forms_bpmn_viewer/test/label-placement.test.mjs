import {test} from 'node:test';import assert from 'node:assert/strict';
import {chooseLabelPosition} from '../public/label-placement.js';
test('nudges an event label clear of the neighbouring task',()=>{
 const label={x:152,y:100,width:130,height:30},task={x:210,y:85,width:200,height:90};
 const p=chooseLabelPosition(label,[task],[],[],{x:100,y:95,width:40,height:40});
 assert.ok(p.x+label.width<=task.x-4 || p.y+label.height<=task.y-4 || p.y>=task.y+task.height+4);
});
test('clear labels do not drift and nudges stay deterministic',()=>{
 const label={x:100,y:100,width:100,height:30};assert.deepEqual(chooseLabelPosition(label,[],[]),{x:100,y:100});
 const lines=[{x:90,y:110,width:200,height:2}];const p=chooseLabelPosition(label,[],lines);
 assert.ok(p.y+30<110 || p.y>112);assert.deepEqual(p,chooseLabelPosition(label,[],lines));
});
