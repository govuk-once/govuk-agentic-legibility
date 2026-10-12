import {test} from 'node:test';
import assert from 'node:assert/strict';
import {sourceQuestions,formFeatures,processForNode} from '../public/metadata.js';
import {createCatalogue} from '../server.mjs';
import fs from 'node:fs/promises';import path from 'node:path';import os from 'node:os';
const metadata={
  "source_sfsm": {
    "id": "test.journey",
    "processes": {
      "main": {
        "states": {
          "question": {
            "type": "input",
            "prompt": "Full prompt",
            "schema": {
              "kind": "boolean"
            }
          },
          "branch": {
            "type": "choice"
          },
          "invoke": {
            "type": "invoke"
          },
          "api": {
            "type": "call"
          }
        }
      },
      "child": {
        "states": {
          "question": {
            "type": "input",
            "prompt": "Other prompt",
            "schema": {
              "kind": "string"
            }
          }
        }
      }
    }
  },
  "questions": {
    "q": {
      "schema": {
        "kind": "boolean"
      }
    }
  }
};
test('SFSM inventories qualify state IDs by process, keeping original prompts',()=>{
 const qs=sourceQuestions(metadata);assert.equal(qs.length,2);assert.equal(qs[0].id,'main/question');assert.equal(qs[1].id,'child/question');assert.equal(qs[0].data.question_text,'Full prompt');assert.equal(qs[1].process_id,'child');
});
test('SFSM catalogue features describe process calls and APIs, not missing Forms data',()=>{
 const features=formFeatures(metadata,{});assert.deepEqual(features.features,['sfsm','linked_processes','service_calls','routing']);assert.deepEqual(features.answerTypes,['boolean','string']);
});
test('process ownership resolves nested scopes and excludes unrelated processes',()=>{
 const nodes=new Map([['main',{id:'main',type:'process'}],['child',{id:'child',type:'process'}],['group',{id:'group',type:'subProcess',parentId:'main'}],['q',{id:'q',type:'userTask',parentId:'group'}]]);
 assert.equal(processForNode({nodes},'q'),'main');assert.equal(processForNode({nodes},'child'),'child');assert.equal(processForNode({nodes},'missing'),null);
});
test('catalogue uses the SFSM journey name and all-process question count',async t=>{
 const dir=await fs.mkdtemp(path.join(os.tmpdir(),'sfsm-viewer-'));t.after(()=>fs.rm(dir,{recursive:true,force:true}));
 await fs.writeFile(path.join(dir,'journey.bpmn'),'<definitions/>');await fs.writeFile(path.join(dir,'journey.questions.json'),JSON.stringify(metadata));await fs.writeFile(path.join(dir,'journey.report.json'),JSON.stringify({model_id:'test.journey',mode:'sfsm',question_count:2}));
 const {forms}=await createCatalogue(dir).list();assert.equal(forms[0].name,'test.journey');assert.equal(forms[0].formId,'test.journey');assert.equal(forms[0].questionCount,2);assert.ok(forms[0].features.includes('linked_processes'));assert.ok(!forms[0].features.includes('unknown'));
});
