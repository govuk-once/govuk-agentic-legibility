export const BPMN_NS = 'http://www.omg.org/spec/BPMN/20100524/MODEL';
export const FORMS_NS = 'urn:govuk:forms:bpmn:visualisation:v1';

export function chooseVariant(variants, preferredMode) {
  return variants.find(v => preferredMode && v.mode === preferredMode) || variants.find(v => v.mode === 'auto') || variants[0] || null;
}

export function sourceQuestions(metadata) {
  return (metadata?.source_export?.content?.steps || []).map(step => ({ ...step, position: step.position ?? '?', data: step.data || {} }));
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
    const extra = (name) => extension ? [...extension.children].find(e => e.namespaceURI === FORMS_NS && e.localName === name) : null;
    const state = extra('state'), decomposition = extra('decomposition'), questionRef = extra('questionRef');
    function parse(element) { if (!element) return null; try { return JSON.parse(element.textContent); } catch { return { unparsed:element.textContent }; } }
    const item = { id, type:element.localName, name:element.getAttribute('name') || element.localName, stateId:extra('stateRef')?.getAttribute('stateId'), questionRef:questionRef?.getAttribute('href'), sourceStepId:questionRef?.getAttribute('sourceStepId'), state:parse(state), decomposition:parse(decomposition), default:element.getAttribute('default'), parentId:element.parentElement?.getAttribute('id') };
    if (item.type === 'sequenceFlow') {
      item.source=element.getAttribute('sourceRef'); item.target=element.getAttribute('targetRef');
      const expr=[...element.children].find(e => e.namespaceURI === BPMN_NS && e.localName === 'conditionExpression');
      item.condition=expr?.textContent || null; item.language=expr?.getAttribute('language') || null;
      flows.push(item);
    }
    nodes.set(id,item);
  }
  return { nodes, flows };
}
