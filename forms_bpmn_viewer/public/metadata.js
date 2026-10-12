export const BPMN_NS = 'http://www.omg.org/spec/BPMN/20100524/MODEL';
export const FORMS_NS = 'urn:govuk:forms:bpmn:visualisation:v1';
export const SFSM_NS = 'urn:govuk:sfsm:bpmn:visualisation:v1';

export function chooseVariant(variants, preferredMode) {
  return variants.find(v => preferredMode && v.mode === preferredMode) || variants.find(v => v.mode === 'auto') || variants[0] || null;
}

export function sourceQuestions(metadata) {
  const definition=metadata?.source_sfsm;
  if(definition?.processes)return Object.entries(definition.processes).flatMap(([pid,p])=>Object.entries(p.states || {}).filter(([,state])=>state.type==='input').map(([sid,state],i)=>({id:pid+'/'+sid,position:i+1,process_id:pid,data:{question_text:state.prompt,answer_type:state.schema?.kind},routing_conditions:[]})));
  const steps=metadata?.source_export?.content?.steps;
  return (Array.isArray(steps) ? steps : []).map(step => ({ ...step, position: step.position ?? '?', data: step.data || {} }));
}

// Only a local matching sidecar is used. Never fetch a questionRef URL from XML.
export function resolveQuestion(reference, metadata, expectedFilename) {
  if (!reference) return { question:null, issue:null };
  const marker = '#/questions/', split = reference.indexOf(marker);
  if (split < 0) return { question:null, issue:'Question reference is not in the supported sidecar format.' };
  if (reference.slice(0,split) !== expectedFilename) return { question:null, issue:'Question reference points to a different sidecar: ' + reference.slice(0,split) };
  const id = reference.slice(split+marker.length);
  const question = metadata?.questions?.[id];
  return { question:question || null, issue:question ? null : 'Question definition is missing from the sidecar.' };
}

export function inspectXml(document) {
  const nodes = new Map(), flows = [];
  for (const element of document.getElementsByTagNameNS(BPMN_NS, '*')) {
    const id = element.getAttribute('id');
    if (!id) continue;
    const extension = [...element.children].find(e => e.namespaceURI === BPMN_NS && e.localName === 'extensionElements');
    const extra = (name) => extension ? [...extension.children].find(e => [FORMS_NS,SFSM_NS].includes(e.namespaceURI) && e.localName === name) : null;
    const state = extra('state'), decomposition = extra('decomposition'), questionRef = extra('questionRef');
    function parse(element) { if (!element) return null; try { return JSON.parse(element.textContent); } catch { return { unparsed:element.textContent }; } }
    const item = { id, type:element.localName, name:element.getAttribute('name') || element.localName, stateId:extra('stateRef')?.getAttribute('stateId'), questionRef:questionRef?.getAttribute('href'), sourceStepId:questionRef?.getAttribute('sourceStepId'), state:parse(state), decomposition:parse(decomposition), default:element.getAttribute('default'), parentId:element.parentElement?.getAttribute('id'), calledElement:element.getAttribute('calledElement'), attachedTo:element.getAttribute('attachedToRef'), sourceProcessId:extra('stateRef')?.getAttribute('processId') || extra('processRef')?.getAttribute('processId') };
    if (item.type === 'sequenceFlow') {
      item.source=element.getAttribute('sourceRef'); item.target=element.getAttribute('targetRef');
      const expr=[...element.children].find(e => e.namespaceURI === BPMN_NS && e.localName === 'conditionExpression');
      item.condition=expr?.textContent || null; item.language=expr?.getAttribute('language') || null;
      flows.push(item);
    }
    nodes.set(id,item);
  }
  const diagrams=[...document.getElementsByTagNameNS('http://www.omg.org/spec/BPMN/20100524/DI','BPMNDiagram')].map(d=>({id:d.getAttribute('id'),processId:d.getElementsByTagNameNS('http://www.omg.org/spec/BPMN/20100524/DI','BPMNPlane')[0]?.getAttribute('bpmnElement')}));
  return { nodes, flows, processes:[...nodes.values()].filter(n=>n.type==='process'), diagrams };
}

// Catalogue features describe source semantics, not generated repeat controls.
export function formFeatures(metadata, report) {
  const steps=sourceQuestions(metadata), known=Array.isArray(metadata?.source_export?.content?.steps) || Boolean(metadata?.source_sfsm?.processes);
  const questions=Object.values(metadata?.questions || {});
  const features=[];
  if (steps.some(q=>q.data.is_repeatable===true)) features.push('repeatable');
  const states=Object.values(metadata?.source_sfsm?.processes || {}).flatMap(p=>Object.values(p.states || {}));
  if(metadata?.source_sfsm){features.push('sfsm');if(states.some(s=>s.type==='invoke'))features.push('linked_processes');if(states.some(s=>s.type==='call'))features.push('service_calls');}
  if (steps.some(q=>q.routing_conditions?.length) || states.some(s=>s.type==='choice')) features.push('routing');
  if (steps.some(q=>q.exit_pages?.length)) features.push('exits');
  if (steps.some(q=>q.data.is_optional===true)) features.push('optional');
  if (known && !features.some(f=>['repeatable','routing','exits'].includes(f))) features.push('linear');
  if (!known) features.push('unknown');
  if (report?.decomposition?.length) features.push('grouped');
  return {features, answerTypes:[...new Set(steps.map(q=>q.data.answer_type).filter(Boolean))].sort(), compiledKinds:[...new Set(questions.filter(q=>!q.generated).map(q=>q.schema?.kind).filter(Boolean))].sort()};
}
export function matchesFilters(form,{query='',feature='',answerType='',compiledKind='',issuesOnly=false}={}) {
  return (!query || (form.name+' '+form.formId+' '+form.folder).toLowerCase().includes(query.toLowerCase())) && (!feature || form.features?.includes(feature)) && (!answerType || form.answerTypes?.includes(answerType)) && (!compiledKind || form.compiledKinds?.includes(compiledKind)) && (!issuesOnly || form.issues.length>0);
}

export function processForNode(model,id) {
 const seen=new Set();let node=model.nodes.get(id);
 while(node && !seen.has(node.id)){
  if(node.type==='process')return node.id;
  seen.add(node.id);node=model.nodes.get(node.parentId);
 }
 return null;
}
