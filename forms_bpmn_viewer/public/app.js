import { chooseVariant, sourceQuestions, resolveQuestion, inspectXml, matchesFilters } from './metadata.js';

import { diagramBounds, fittedViewbox, focusedViewbox } from './viewport.js';

const $ = (id) => document.getElementById(id);
const viewer = new window.BpmnJS({ container:$('canvas') });
const state = { forms:[], form:null, variant:null, payload:null, model:null, selected:null, tab:'selection', request:0, preferredMode:null, markers:[], page:0, pageSize:30, questionNodes:new Map() };
function dom(tag, text, className) { const e=document.createElement(tag); if (text !== undefined && text !== null) e.textContent=String(text); if (className) e.className=className; return e; }
function button(text, action, className) { const e=dom('button',text,className); e.type='button'; e.addEventListener('click',action); return e; }
function raw(value) { return dom('pre',typeof value === 'string' ? value : JSON.stringify(value,null,2),'raw-json'); }
function section(title, child) { const e=dom('section',null,'section'); e.append(dom('h3',title)); if (child) e.append(child); return e; }
function details(title,value) { const e=dom('details'); e.append(dom('summary',title),raw(value)); return e; }
function fields(entries) { const e=dom('dl',null,'fields'); for (const [label,value] of entries) { if (value === undefined || value === null) continue; e.append(dom('dt',label),dom('dd',typeof value === 'object' ? JSON.stringify(value) : value)); } return e; }
function note(text) { return dom('p',text,'warning-note'); }
async function api(url) { const response=await fetch(url); const value=await response.json(); if (!response.ok) throw new Error(value.error || response.statusText); return value; }
function tab(name) { state.tab=name; for (const id of ['selection','questions','report','source']) { $('tab-'+id).setAttribute('aria-selected',String(id===name)); $('tab-'+id).tabIndex=id===name ? 0 : -1; $('panel-'+id).hidden=id!==name; } }
for (const name of ['selection','questions','report','source']) $('tab-'+name).addEventListener('click',() => tab(name));
const tabNames=['selection','questions','report','source'];
document.querySelector('.inspector-tabs').addEventListener('keydown',event => { if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return; event.preventDefault(); const i=tabNames.indexOf(state.tab); const n=event.key==='Home' ? 0 : event.key==='End' ? 3 : (i+(event.key==='ArrowRight' ? 1 : 3))%4; tab(tabNames[n]); $('tab-'+tabNames[n]).focus(); });

const featureNames={repeatable:'Repeatable questions',routing:'Conditional routing',exits:'Exit pages',optional:'Optional questions',linear:'Linear (no routing or repeats)',grouped:'Automatically grouped',unknown:'Missing source metadata',failed:'Not converted'};
function filterOptions() {
  for (const [id,field,names] of [['feature-filter','features',featureNames],['answer-filter','answerTypes',{}],['kind-filter','compiledKinds',{}]]) {
    const select=$(id), previous=select.value; select.replaceChildren(new Option('All',''));
    const values=[...new Set(state.forms.flatMap(f=>f[field] || []))].sort();
    for (const value of values) select.append(new Option(`${names[value] || value} (${state.forms.filter(f=>f[field]?.includes(value)).length})`,value));
    if (values.includes(previous)) select.value=previous;
  }
}
function filteredForms() { return state.forms.filter(form=>matchesFilters(form,{query:$('search').value.trim(),feature:$('feature-filter').value,answerType:$('answer-filter').value,compiledKind:$('kind-filter').value,issuesOnly:$('issues-only').checked})); }
function renderCatalogue() {
  const forms=filteredForms(); $('form-list').replaceChildren(); $('catalogue-count').textContent=`${forms.length} of ${state.forms.length} forms`;
  const pages=Math.max(1,Math.ceil(forms.length/state.pageSize)); state.page=Math.min(state.page,pages-1);
  for (const form of forms.slice(state.page*state.pageSize,(state.page+1)*state.pageSize)) {
    const card=button('',() => openForm(form),'form-card'+(state.form?.id===form.id ? ' active' : ''));
    card.setAttribute('aria-label',`Form ${form.formId}: ${form.name}`); card.setAttribute('aria-current',String(state.form?.id===form.id));
    card.append(dom('span','FORM '+form.formId,'eyebrow'),dom('strong',form.name));
    const meta=dom('div',null,'card-meta');
    meta.append(dom('span',form.questionCount === null ? 'No question metadata' : `${form.questionCount} questions`,'badge'));
    meta.append(dom('span',`${form.variants.length} ${form.variants.length===1 ? 'view' : 'views'}`,'badge'));
    if (form.issues.length) meta.append(dom('span',form.variants.length ? 'Check warnings' : 'Not converted','badge warning'));
    for (const f of ['repeatable','routing','exits','grouped']) if (form.features?.includes(f)) meta.append(dom('span',featureNames[f],'badge'));
    card.append(meta); $('form-list').append(card);
  }
  if (!forms.length) $('form-list').append(dom('p',state.forms.length ? 'No matching forms.' : 'No generated forms found. Generate BPMN, then click Refresh.','muted'));
  $('page-label').textContent=`Page ${state.page+1} of ${pages}`;
  $('page-previous').disabled=state.page===0; $('page-next').disabled=state.page>=pages-1;
}
for (const id of ['search','issues-only','feature-filter','answer-filter','kind-filter']) $(id).addEventListener(id==='search' ? 'input' : 'change',()=>{state.page=0;renderCatalogue();});
$('clear-filters').addEventListener('click',()=>{for(const id of ['search','feature-filter','answer-filter','kind-filter']) $(id).value='';$('issues-only').checked=false;state.page=0;renderCatalogue();});
$('page-previous').addEventListener('click',()=>{state.page--;renderCatalogue();$('form-list').scrollTop=0;});
$('page-next').addEventListener('click',()=>{state.page++;renderCatalogue();$('form-list').scrollTop=0;});

function notices(items) { const messages=[...new Set(items.filter(Boolean))]; $('notices').replaceChildren(...messages.map(message => dom('div',message))); $('notices').hidden=!messages.length; }
function empty(message) { const e=$('canvas-empty'); e.hidden=false; e.replaceChildren(dom('span','◇','empty-icon'),dom('h3',message),dom('p','Choose another diagram or inspect the conversion report.')); }
function controls(enabled) { for (const id of ['zoom-in','zoom-out','fit','readable','focus','download']) $(id).disabled=!enabled; $('previous').disabled=true; $('next').disabled=true; }
function zoomLabel() { try { $('zoom-label').textContent=Math.round(viewer.get('canvas').zoom()*100)+'%'; } catch { /* before import */ } }
viewer.on('canvas.viewbox.changed',zoomLabel);
viewer.on('element.click',event => { if (event.element?.id && state.model?.nodes.has(event.element.id)) selectElement(event.element.id,false); });
viewer.on('selection.changed',event => { const item=event.newSelection?.[0]; if (item && item.id!==state.selected && state.model?.nodes.has(item.id)) selectElement(item.id,false); });

function applyViewbox(box) { if (!box) return; viewer.get('canvas').viewbox(box); zoomLabel(); }
function fitJourney() {
  // Include shape, label and connection coordinates. Avoid cached SVG bounds,
  // and reset the transform directly so a previous invalid zoom cannot persist.
  const canvas=viewer.get('canvas');
  applyViewbox(fittedViewbox(diagramBounds(viewer.get('elementRegistry').getAll()),canvas.getSize()));
}
function focusElement(id, scale='readable') {
  const element=viewer.get('elementRegistry').get(id); if (!element) return;
  if (element.waypoints) { if (element.source) focusElement(element.source.id,scale); return; }
  const size=viewer.get('canvas').getSize();
  applyViewbox(scale==='fit-node' ? fittedViewbox(element,size,50,1.3) : focusedViewbox(element,size));
}
function readable() {
  const current=viewer.get('elementRegistry').get(state.selected);
  const id=current && !current.waypoints && current.type!=='bpmn:SubProcess' ? current.id : state.questionNodes.values().next().value;
  if (id) focusElement(id); else fitJourney();
}
function zoomBy(factor) {
  const canvas=viewer.get('canvas'),box=canvas.viewbox(false);
  if (![box.x,box.y,box.width,box.height,box.scale].every(Number.isFinite) || box.scale<=0) return fitJourney();
  const size=canvas.getSize(),scale=Math.min(4,Math.max(.001,box.scale*factor));
  applyViewbox(fittedViewbox({x:box.x+box.width/2,y:box.y+box.height/2,width:0,height:0},size,0,scale));
}
$('zoom-in').addEventListener('click',()=>zoomBy(1.3));
$('zoom-out').addEventListener('click',()=>zoomBy(1/1.3));
$('fit').addEventListener('click',fitJourney);
$('readable').addEventListener('click',readable);
$('focus').addEventListener('click',() => { if (state.selected) focusElement(state.selected,'fit-node'); else readable(); });
function download(text, filename, type='text/plain') { const url=URL.createObjectURL(new Blob([text],{type})); const link=dom('a'); link.href=url; link.download=filename; link.click(); setTimeout(() => URL.revokeObjectURL(url),1000); }
$('download').addEventListener('click',() => { if (state.payload) download(state.payload.xml,state.payload.filename,'application/xml'); });

function buildQuestionIndex() {
  state.questionNodes=new Map();
  for (const node of state.model.nodes.values()) {
    if (node.type!=='userTask') continue;
    const { question }=resolveQuestion(node.questionRef,state.payload.questions,state.payload.filename.replace(/\.bpmn$/,'.questions.json'));
    if (question && !question.generated && question.source_step_id) state.questionNodes.set(question.source_step_id,node.id);
    else if (!question && node.sourceStepId && !state.questionNodes.has(node.sourceStepId)) state.questionNodes.set(node.sourceStepId,node.id);
  }
  // Expanded subprocesses change XML order. Question navigation must keep the
  // original export order rather than jumping to the shared questions first.
  const found = state.questionNodes;
  state.questionNodes = new Map(sourceQuestions(state.payload.questions)
    .filter(question => found.has(question.id))
    .map(question => [question.id, found.get(question.id)]));
  for (const [sourceId, nodeId] of found) if (!state.questionNodes.has(sourceId)) state.questionNodes.set(sourceId, nodeId);
}
async function openForm(form, variant=null, preserveQuestion=null) {
  const token=++state.request; state.form=form; state.variant=variant || chooseVariant(form.variants,state.preferredMode); state.payload=null; state.model=null; state.selected=null;
  controls(false); $('representation-help').textContent=''; renderCatalogue(); clearMarkers(); viewer.clear(); $('diagram-status').textContent='Loading…'; $('filename').textContent='';
  $('form-id').textContent='FORM '+form.formId; $('form-title').textContent=form.name; $('form-summary').textContent=(form.questionCount ?? 'Unknown number of')+' questions · select a node to inspect';
  for (const id of ['selection','questions','report','source']) $('panel-'+id).replaceChildren(dom('p','Loading…','muted'));
  $('variants').replaceChildren();
  for (const v of form.variants) { const b=button(v.mode==='auto' ? (v.groups===0 ? 'Auto (no groups)' : 'Grouped') : v.mode==='flat' ? 'Flat' : v.filename,() => { const q=selectedSourceId(); state.preferredMode=v.mode; openForm(form,v,q); },v.id===state.variant?.id ? 'active' : ''); b.title=(v.mode==='auto' ? 'Converter output with safely inferred routing regions shown as expanded subprocesses. No questions are hidden. ' : v.mode==='flat' ? 'Every question and route shown without subprocess grouping. ' : '')+v.filename; b.setAttribute('aria-pressed',String(v.id===state.variant?.id)); $('variants').append(b); }
  notices(form.issues); $('canvas-empty').hidden=true;
  if (!state.variant) {
    empty('This form has no generated BPMN'); $('diagram-status').textContent='Conversion did not produce a diagram';
    $('panel-selection').replaceChildren(note('No diagram available. See Report for the conversion log.'));
    $('panel-questions').replaceChildren(dom('p','No question sidecar available.','muted'));
    $('panel-source').replaceChildren(dom('p','No source metadata available.','muted'));
    renderReport(null); await addLog(form,token); return;
  }
  try {
    const payload=await api(`/api/forms/${form.id}/variants/${state.variant.id}`);
    if (token!==state.request) return;
    // Serialise actual imports; bpmn-js mutates a shared canvas asynchronously.
    importQueue=importQueue.catch(() => {}).then(async () => {
      if (token!==state.request) return;
      const doc=new DOMParser().parseFromString(payload.xml,'application/xml');
      if (doc.querySelector('parsererror')) throw new Error('The BPMN XML is not well formed.');
      const result=await viewer.importXML(payload.xml);
      if (token!==state.request) { viewer.clear(); return; }
      state.payload=payload; state.model=inspectXml(doc); buildQuestionIndex();
      viewer.get('canvas').resized();
      const warnings=(result.warnings || []).map(w => w.message);
      notices([...form.issues,...payload.issues,...warnings]); $('filename').textContent=payload.filename;
      controls(true); $('canvas-empty').hidden=true; $('diagram-status').textContent='Click a question or decision. Blue lines show its connected routes.';
      $('form-summary').textContent=`${form.questionCount ?? state.questionNodes.size} source questions · ${payload.report?.decomposition?.length ?? 0} groups · ${state.variant.mode==='flat' ? 'flat view' : state.variant.mode==='auto' ? 'automatic grouping' : 'diagram view'}`;
      $('representation-help').textContent=state.variant.mode==='auto' ? (payload.report?.decomposition?.length ? 'Grouped: inferred routing regions are outlined as expanded subprocesses. All questions remain visible; see Report for reasons.' : 'Auto: no safe grouping was inferred. This form remains flat.') : state.variant.mode==='flat' ? 'Flat: questions and routes without subprocess grouping.' : 'Diagram as generated; select a node to inspect its BPMN type.';
      renderQuestions(); renderReport(payload.report); renderSource();
      const first=preserveQuestion && state.questionNodes.get(preserveQuestion) || state.questionNodes.values().next().value;
      if (first) selectElement(first,true); else { fitJourney(); renderSelection(null); }
      await addLog(form,token);
      const hash=new URLSearchParams({form:form.id,variant:state.variant.id}); if (preserveQuestion) hash.set('question',preserveQuestion);
      history.replaceState(null,'','#'+hash);
    });
    await importQueue;
  } catch (error) { if (token!==state.request) return; controls(false); empty('Unable to display this BPMN'); notices([...form.issues,error.message]); $('diagram-status').textContent='Diagram import failed'; $('panel-selection').replaceChildren(note(error.message)); renderReport(null); $('panel-questions').replaceChildren(dom('p','Diagram import failed.','muted')); $('panel-source').replaceChildren(raw(error.message)); await addLog(form,token); }
}
let importQueue=Promise.resolve();
function clearMarkers() { const canvas=viewer.get('canvas'); for (const [id,marker] of state.markers) { try { canvas.removeMarker(id,marker); } catch { /* old diagram */ } } state.markers=[]; }
function mark(id,marker) { if (!viewer.get('elementRegistry').get(id)) return; viewer.get('canvas').addMarker(id,marker); state.markers.push([id,marker]); }
function selectedSourceId() { const node=state.model?.nodes.get(state.selected); return node?.sourceStepId || node?.stateId?.split('__')[0] || null; }
function selectElement(id, move) {
  const node=state.model?.nodes.get(id); if (!node) return; state.selected=id; clearMarkers(); mark(id,'inspected');
  for (const flow of state.model.flows.filter(f => f.source===id || f.target===id || f.id===id)) { mark(flow.id,'route-highlight'); if (flow.source!==id) mark(flow.source,'route-neighbour'); if (flow.target!==id) mark(flow.target,'route-neighbour'); }
  viewer.get('selection').select(viewer.get('elementRegistry').get(id));
  if (move) focusElement(id,node.type==='subProcess' ? 'fit-node' : 'readable');
  renderSelection(node); renderQuestions(); tab('selection'); updateQuestionNavigation();
  if (state.form && state.variant) { const hash=new URLSearchParams({form:state.form.id,variant:state.variant.id}); const q=selectedSourceId(); if (q) hash.set('question',q); history.replaceState(null,'','#'+hash); }
}
function updateQuestionNavigation() { const keys=[...state.questionNodes.keys()], i=keys.indexOf(selectedSourceId()); $('previous').disabled=i<=0; $('next').disabled=i<0 || i>=keys.length-1; }
function stepQuestion(direction) { const keys=[...state.questionNodes.keys()], i=keys.indexOf(selectedSourceId()), target=keys[i+direction]; if (target) selectElement(state.questionNodes.get(target),true); }
$('previous').title='Previous source question in export order, including alternative branches'; $('next').title='Next source question in export order, including alternative branches';
$('previous').addEventListener('click',() => stepQuestion(-1)); $('next').addEventListener('click',() => stepQuestion(1));

function renderSelection(node) {
  const panel=$('panel-selection'); panel.replaceChildren(); panel.scrollTop=0;
  if (!node) { panel.append(dom('h2','Inspect a node'),dom('p','Click a question, decision or connecting arrow.','muted')); return; }
  const kinds={userTask:'Question / user task',exclusiveGateway:'Exclusive gateway',subProcess:'Expanded subprocess',sequenceFlow:'Sequence flow',scriptTask:'Collection operation',task:'Display task',startEvent:'Start',endEvent:'End'};
  panel.append(dom('p',kinds[node.type] || node.type,'node-kind'),dom('h2',node.name,'node-name'),dom('p',node.id,'identifier'));
  if (node.stateId) panel.append(dom('p','Source state: '+node.stateId,'identifier'));
  const { question, issue }=resolveQuestion(node.questionRef,state.payload.questions,state.payload.filename.replace(/\.bpmn$/,'.questions.json'));
  if (issue) panel.append(note(issue));
  const original=sourceQuestions(state.payload.questions).find(q => q.id===(question?.source_step_id || node.sourceStepId || node.stateId?.split('__')[0]));
  if (question) {
    const presentation=question.schema?.presentation || {};
    panel.append(fields([['Source step',question.source_step_id],['Answer type',presentation.answer_type],['Compiled kind',question.schema?.kind],['Required',presentation.required===false ? 'No' : 'Yes'],['Repeatable',presentation.is_repeatable ? 'Yes' : 'No'],['Generated control',question.generated ? 'Yes — added by the Forms adapter' : 'No'],['Assignment',question.assign]]));
    if (presentation.page_heading) panel.append(section('Page heading',dom('p',presentation.page_heading,'prose')));
    if (presentation.hint_text) panel.append(section('Hint',dom('p',presentation.hint_text,'prose')));
    if (presentation.guidance_markdown) panel.append(section('Guidance (source Markdown)',dom('div',presentation.guidance_markdown,'prose')));
    const options=question.schema?.options;
    if (options?.length) { const list=dom('div'); for (const o of options) list.append(dom('p',(o.label || o.name || o.value || o)+' '+(o.value !== undefined ? `(${o.value})` : ''),'prose')); panel.append(section('Compiled answer options',list)); }
    if (presentation.answer_settings) panel.append(section('Original answer settings',raw(presentation.answer_settings)));
    panel.append(details('Full compiled question definition',question));
  } else if (node.type==='userTask') panel.append(note('No linked question definition. The diagram still displays, but detailed question settings are unavailable.'));
  if (original) { panel.append(section('Source question',dom('p',original.data.question_text,'prose'))); if (original.routing_conditions?.length) panel.append(section('Original routing conditions',raw(original.routing_conditions))); if (original.exit_pages?.length) panel.append(section('Original exit pages',raw(original.exit_pages))); panel.append(details('Original export step',original)); }
  if (node.decomposition) { panel.append(section('Why this group exists',dom('p',node.decomposition.reason || 'No reason recorded','prose'))); const members=dom('div'); for (const id of node.decomposition.members || []) { const member=state.model.nodes.get(id); if (member?.type==='userTask') members.append(button(member.name,() => selectElement(id,true),'question-row')); } panel.append(section('Questions in this group',members),details('Decomposition metadata',node.decomposition)); }
  if (node.state) panel.append(section(node.type==='endEvent' ? 'Completion / exit meaning' : 'Process state',raw(node.state)));
  if (node.type==='sequenceFlow') { panel.append(fields([['Expression language',node.language],['Default route',state.model.nodes.get(node.source)?.default===node.id ? 'Yes' : 'No']])); if (node.condition) panel.append(section('Condition',raw(node.condition))); panel.append(section('Connects',routeCard(node))); }
  else {
    const outgoing=state.model.flows.filter(f => f.source===node.id), incoming=state.model.flows.filter(f => f.target===node.id);
    if (outgoing.length) { const box=dom('div'); outgoing.forEach(flow => box.append(routeCard(flow))); panel.append(section('Outgoing routes',box)); }
    if (incoming.length) { const box=dom('div'); for (const flow of incoming) box.append(button(state.model.nodes.get(flow.source)?.name || flow.source,() => selectElement(flow.source,true),'question-row')); panel.append(section('Incoming from',box)); }
  }
}
function routeCard(flow) {
  const card=dom('div',null,'route'); const isDefault=state.model.nodes.get(flow.source)?.default===flow.id;
  card.append(dom('span',flow.name==='sequenceFlow' ? 'Continue' : flow.name,'route-label'));
  if (isDefault) card.append(dom('p','Default — used when no condition matches.','muted'));
  if (flow.condition) card.append(details('Condition expression',flow.condition));
  if (flow.source===state.selected && state.model.nodes.get(flow.target)?.type==='endEvent') card.append(dom('p','Reaches an end event. Inspect its outcome to distinguish completion from an exit.','muted'));
  card.append(button('→ '+(state.model.nodes.get(flow.target)?.name || flow.target),() => selectElement(flow.target,true)));
  if (flow.id!==state.selected) card.append(button('Inspect this connection',() => selectElement(flow.id,true)));
  else card.append(button('← '+(state.model.nodes.get(flow.source)?.name || flow.source),() => selectElement(flow.source,true)));
  return card;
}
function renderQuestions() {
  const panel=$('panel-questions'); panel.replaceChildren(dom('h2','Source questions'),dom('p','Export order includes alternative branches; this list is not an executed path.','muted'));
  const questions=sourceQuestions(state.payload?.questions);
  if (!questions.length) { panel.append(note('No source question inventory is available.')); return; }
  for (const q of questions) { const id=state.questionNodes.get(q.id); const row=button('',() => { if (id) selectElement(id,true); },'question-row'+(selectedSourceId()===q.id ? ' active' : '')); row.disabled=!id; row.append(dom('span','Q'+q.position,'qnum')); const text=dom('span',q.data.question_text,'qtext'); text.append(dom('small',[q.data.answer_type,q.data.is_optional ? 'optional' : 'required',q.data.is_repeatable ? 'repeatable' : '',q.routing_conditions?.length ? `${q.routing_conditions.length} routes` : ''].filter(Boolean).join(' · '))); row.append(text); panel.append(row); }
}
function renderReport(report) {
  const panel=$('panel-report'); panel.replaceChildren(dom('h2','Conversion report'));
  if (!report) panel.append(note('No conversion report is available.'));
  else {
    panel.append(fields([['Form',report.form_id],['Representation',report.mode],['Source questions',report.question_count],['Groups',report.decomposition?.length ?? 0]]));
    for (const warning of report.warnings || []) panel.append(note(warning));
    if (!report.decomposition?.length) panel.append(section('Decomposition',dom('p','No subprocess grouping was inferred. A linear form may be best kept flat.','prose')));
    for (const group of report.decomposition || []) { const card=dom('div',null,'group-card'); card.append(dom('h3',state.model?.nodes.get(group.id)?.name || 'Subprocess'),dom('p',group.reason,'prose'),dom('p','Questions: '+(group.question_ids || []).join(', '),'identifier')); if (state.model?.nodes.has(group.id)) card.append(button('Show group in diagram',() => selectElement(group.id,true))); panel.append(card); }
    panel.append(details('Raw conversion report',report));
  }
  panel.append(dom('div',null,'log-placeholder'));
}
async function addLog(form,token) { if (!form.hasLog) return; try { const value=await api(`/api/forms/${form.id}/log`); if (token===state.request) $('panel-report').append(details('Conversion log',value.log || 'No log content')); } catch(error) { if (token===state.request) $('panel-report').append(note(error.message)); } }
function renderSource() {
  const panel=$('panel-source'); panel.replaceChildren(dom('h2','Original source and metadata'),dom('p','The source export is retained in the question sidecar. Settings shown here are not validation performed by this viewer.','muted'));
  const tools=dom('div',null,'source-tools');
  if (state.payload.questions) tools.append(button('Download question metadata',() => download(JSON.stringify(state.payload.questions,null,2),state.payload.filename.replace(/\.bpmn$/,'.questions.json'),'application/json')));
  if (state.payload.report) tools.append(button('Download report',() => download(JSON.stringify(state.payload.report,null,2),state.payload.filename.replace(/\.bpmn$/,'.report.json'),'application/json')));
  panel.append(section('Downloads',tools));
  const source=state.payload.questions?.source_export;
  if (source) { panel.append(details('Original form export',source),details('All compiled question definitions',state.payload.questions.questions)); }
  else panel.append(note('Original source export is missing from this sidecar.'));
  panel.append(details('BPMN XML',state.payload.xml));
}
async function refresh(force=false) {
  $('refresh').disabled=true;
  try {
    const catalogue=await api('/api/forms'+(force ? '?refresh=1' : '')); state.forms=catalogue.forms; filterOptions(); $('directory').textContent=catalogue.directory; renderCatalogue();
    if (catalogue.notice) notices([catalogue.notice]);
    if (!force && !state.form) { const hash=new URLSearchParams(location.hash.slice(1)), form=state.forms.find(f => f.id===hash.get('form')) || state.forms.find(f => f.variants.length); if (form) await openForm(form,form.variants.find(v => v.id===hash.get('variant')),hash.get('question')); }
    else if (force && state.form) { const selected=state.forms.find(f => f.id===state.form.id); if (selected) await openForm(selected,selected.variants.find(v => v.id===state.variant?.id),selectedSourceId()); else { state.form=null; renderCatalogue(); empty('Selected form is no longer in the catalogue'); controls(false); } }
  } catch(error) { $('catalogue-count').textContent='Unable to load catalogue'; notices([error.message]); }
  finally { $('refresh').disabled=false; }
}
$('refresh').addEventListener('click',() => refresh(true));
new ResizeObserver(() => { try { viewer.get('canvas').resized(); } catch { /* initial empty canvas */ } }).observe($('canvas'));
refresh();
