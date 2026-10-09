import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { createCatalogue, createServer } from '../server.mjs';
import { chooseVariant, resolveQuestion, sourceQuestions } from '../public/metadata.js';

async function corpus(t) {
  const directory=await fs.mkdtemp(path.join(os.tmpdir(),'forms-viewer-'));
  t.after(() => fs.rm(directory,{ recursive:true, force:true }));
  return directory;
}
async function put(root,folder,stem='form',mode='auto') {
  const dir=path.join(root,folder); await fs.mkdir(dir,{ recursive:true });
  await fs.writeFile(path.join(dir,stem+'.bpmn'),'<bpmn:definitions/>');
  await fs.writeFile(path.join(dir,stem+'.questions.json'),JSON.stringify({ form_id:7530, source_export:{content:{name:'DVSA logo application',steps:[{ id:'q1',position:1,data:{question_text:'Trainer type?',answer_type:'selection'}}]}},questions:{state_q1:{source_step_id:'q1',schema:{kind:'select_one'}}}}));
  await fs.writeFile(path.join(dir,stem+'.report.json'),JSON.stringify({form_id:'7530',mode,question_count:1,decomposition:[{id:'group',reason:'single entry'}]}));
}

test('directory-per-form catalogue joins variants and reads source name',async t => {
  const root=await corpus(t); await put(root,'7530','flat','flat'); await put(root,'7530','auto','auto');
  const catalogue=createCatalogue(root), list=await catalogue.list();
  assert.equal(list.forms.length,1); const form=list.forms[0];
  assert.equal(form.name,'DVSA logo application'); assert.equal(form.questionCount,1); assert.equal(form.variants.length,2);
  assert.equal(form.variants[0].mode,'auto'); assert.equal(form.variants[0].groups,1);
  const payload=await catalogue.load(form.id,form.variants[0].id);
  assert.equal(payload.questions.form_id,7530); assert.equal(payload.report.mode,'auto'); assert.match(payload.xml,/definitions/);
});

test('single form.bpmn and numbered export filenames are both supported',async t => {
  const root=await corpus(t); await put(root,'6'); await put(root,'7530','7530.auto');
  const list=await createCatalogue(root).list(); assert.equal(list.forms.length,2);
  assert.deepEqual(list.forms.flatMap(f => f.variants.map(v => v.filename)).sort(),['7530.auto.bpmn','form.bpmn']);
});

test('missing metadata and failed conversions stay visible',async t => {
  const root=await corpus(t); await fs.mkdir(path.join(root,'broken'));
  await fs.writeFile(path.join(root,'broken','form.bpmn'),'bad XML');
  await fs.writeFile(path.join(root,'broken','conversion.log'),'UNSUPPORTED: missing destination');
  await fs.mkdir(path.join(root,'no-diagram')); await fs.writeFile(path.join(root,'no-diagram','conversion.log'),'UNSUPPORTED: payment');
  const catalogue=createCatalogue(root), list=await catalogue.list();
  assert.equal(list.forms.length,2);
  const broken=list.forms.find(f => f.folder==='broken');
  assert.equal(broken.issues.length,3); assert.match(broken.issues[2],/stale/);
  const data=await catalogue.load(broken.id,broken.variants[0].id); assert.equal(data.questions,null); assert.equal(data.issues.length,2);
  const failure=list.forms.find(f => f.folder==='no-diagram'); assert.equal(failure.variants.length,0); assert.match(await catalogue.log(failure.id),/payment/);
});

test('malformed sidecars are reported rather than hiding diagrams',async t => {
  const root=await corpus(t); await put(root,'7530'); await fs.writeFile(path.join(root,'7530','form.questions.json'),'{broken');
  const list=await createCatalogue(root).list(); assert.equal(list.forms.length,1); assert.match(list.forms[0].issues[0],/Cannot read/);
});

test('catalogue is cached and explicit refresh discovers new forms',async t => {
  const root=await corpus(t), catalogue=createCatalogue(root);
  assert.equal((await catalogue.list()).forms.length,0); await put(root,'7530');
  assert.equal((await catalogue.list()).forms.length,0); assert.equal((await catalogue.list(true)).forms.length,1);
});

test('missing directory returns an actionable empty catalogue',async t => {
  const root=await corpus(t); const list=await createCatalogue(path.join(root,'not-created')).list();
  assert.deepEqual(list.forms,[]); assert.match(list.notice,/does not exist/);
});

test('symlink sidecars outside the corpus are rejected',async t => {
  const root=await corpus(t), outside=await corpus(t); await put(root,'7530');
  const target=path.join(root,'7530','form.questions.json'); await fs.unlink(target); await fs.writeFile(path.join(outside,'secret.json'),'{"secret":true}'); await fs.symlink(path.join(outside,'secret.json'),target);
  const list=await createCatalogue(root).list(); assert.match(list.forms[0].issues[0],/outside/);
});

test('API reads only indexed files, rejects writes and serves local assets',async t => {
  const root=await corpus(t); await put(root,'7530'); const server=createServer(root);
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve)); t.after(() => new Promise(resolve => server.close(resolve)));
  const base='http://127.0.0.1:'+server.address().port;
  const forms=await (await fetch(base+'/api/forms')).json(); const form=forms.forms[0], variant=form.variants[0];
  const good=await fetch(base+`/api/forms/${form.id}/variants/${variant.id}`); assert.equal(good.status,200);
  assert.match(good.headers.get('content-security-policy'),/default-src 'self'/);
  assert.equal((await fetch(base+'/api/forms/unknown/variants/unknown')).status,404);
  assert.equal((await fetch(base+'/api/forms',{method:'POST'})).status,405);
  assert.equal((await fetch(base+'/server.mjs')).status,404);
  assert.equal((await fetch(base+'/vendor/assets/%2e%2e%2f%2e%2e%2fserver.mjs')).status,404);
  assert.match(await (await fetch(base+'/')).text(),/Forms journey explorer/);
  assert.equal((await fetch(base+'/vendor/bpmn.js')).status,200);
});

test('large catalogue is indexed without loading all diagrams',async t => {
  const root=await corpus(t);
  for (let i=0;i<505;i++) { const dir=path.join(root,String(i)); await fs.mkdir(dir); await fs.writeFile(path.join(dir,'form.bpmn'),'invalid XML: deliberately not parsed during listing'); }
  const list=await createCatalogue(root).list(); assert.equal(list.forms.length,505); assert.equal(list.forms[0].folder,'0'); assert.equal(list.forms.at(-1).folder,'504');
});

test('auto view preferred, requested mode preserved, missing mode falls back',() => {
  const variants=[{id:'a',mode:'flat'},{id:'b',mode:'auto'}];
  assert.equal(chooseVariant(variants).id,'b'); assert.equal(chooseVariant(variants,'flat').id,'a'); assert.equal(chooseVariant([variants[0]],'auto').id,'a'); assert.equal(chooseVariant([]),null);
});

test('question references resolve only the matching local sidecar',() => {
  const metadata={questions:{state_q1:{generated:false}}};
  assert.equal(resolveQuestion('form.questions.json#/questions/state_q1',metadata,'form.questions.json').question.generated,false);
  assert.match(resolveQuestion('https://outside.invalid/metadata#/questions/state_q1',metadata,'form.questions.json').issue,/different sidecar/);
  assert.match(resolveQuestion('form.questions.json#/questions/missing',metadata,'form.questions.json').issue,/missing/);
  assert.deepEqual(sourceQuestions(null),[]);
});

test('catalogue merges feature sets across views without double-counting or labelling repeats as routing',async t=>{
 const root=await corpus(t);await put(root,'7530','flat','flat');await put(root,'7530','auto','auto');
 const file=path.join(root,'7530','flat.questions.json');
 const metadata=JSON.parse(await fs.readFile(file,'utf8'));metadata.source_export.content.steps[0].data.is_repeatable=true;
 await fs.writeFile(file,JSON.stringify(metadata));await fs.writeFile(path.join(root,'7530','auto.questions.json'),JSON.stringify(metadata));
 const form=(await createCatalogue(root).list()).forms[0];
 assert.deepEqual(form.answerTypes,['selection']);assert.deepEqual(form.compiledKinds,['select_one']);
 assert.ok(form.features.includes('repeatable'));assert.ok(form.features.includes('grouped'));assert.ok(!form.features.includes('routing'));assert.ok(!form.features.includes('linear'));
});
