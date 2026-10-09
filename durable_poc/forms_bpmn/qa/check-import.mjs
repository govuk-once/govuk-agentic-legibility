// Independently parse BPMN with bpmn.io's model library. Reject any warnings.
import fs from 'node:fs/promises';
import { BpmnModdle } from 'bpmn-moddle';
if (process.argv.length < 3) throw new Error('Usage: node check-import.mjs file.bpmn ...');
for (const path of process.argv.slice(2)) {
  const { rootElement, warnings } = await new BpmnModdle().fromXML(await fs.readFile(path, 'utf8'));
  if (warnings.length) throw new Error(`${path}: ${warnings.map(w => w.message).join('; ')}`);
  if (!rootElement.diagrams?.length) throw new Error(`${path}: no BPMN diagram`);
  console.log(`${path}: bpmn-moddle import OK, 0 warnings`);
}
