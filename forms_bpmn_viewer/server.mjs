import { formFeatures } from './public/metadata.js';
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const appDirectory = path.dirname(fileURLToPath(import.meta.url));
const publicDirectory = path.join(appDirectory, 'public');
const vendorDirectory = path.join(appDirectory, 'node_modules/bpmn-js/dist');
const key = (value) => Buffer.from(value).toString('base64url');
const contained = (root, candidate) => candidate === root || candidate.startsWith(root + path.sep);

// Every data read is constrained to the configured corpus, including symlinks.
async function safeRead(root, filename) {
  const realRoot = await fs.realpath(root);
  const realFile = await fs.realpath(filename);
  if (!contained(realRoot, realFile)) throw new Error('File is outside the configured forms folder');
  return fs.readFile(realFile, 'utf8');
}

async function sidecar(root, filename) {
  try { return { value: JSON.parse(await safeRead(root, filename)), issue: null }; }
  catch (error) { return { value: null, issue: error.code === 'ENOENT' ? `Missing ${path.basename(filename)}` : `Cannot read ${path.basename(filename)}: ${error.message}` }; }
}

export function createCatalogue(rootDirectory) {
  const root = path.resolve(rootDirectory);
  let index = null;
  let scanning = null;
  async function scan() {
    const forms = [], lookup = new Map();
    let directories;
    try { directories = await fs.readdir(root, { withFileTypes: true }); }
    catch (error) {
      if (error.code !== 'ENOENT') throw error;
      return { forms: [], lookup, notice: 'Forms folder does not exist yet. Generate files here, then refresh.', directory: root };
    }
    const groups = [{ name: '(root)', directory: root }, ...directories.filter(d => d.isDirectory()).map(d => ({ name: d.name, directory: path.join(root, d.name) }))];
    // Metadata is inspected once per refresh; BPMN XML is loaded only on selection.
    for (const group of groups) {
      const files = (await fs.readdir(group.directory, { withFileTypes: true })).filter(f => f.isFile() && f.name.endsWith('.bpmn')).sort((a,b) => a.name.localeCompare(b.name));
      let log = null;
      try { log = await safeRead(root, path.join(group.directory, 'conversion.log')); } catch { /* optional */ }
      if (!files.length && !log) continue;
      const form = { id: key(group.name), folder: group.name, formId: group.name, name: group.name, variants: [], questionCount: null, issues: [], hasLog: Boolean(log), features:[], answerTypes:[], compiledKinds:[] };
      for (const file of files) {
        const stem = file.name.slice(0, -5);
        const questions = await sidecar(root, path.join(group.directory, stem + '.questions.json'));
        const report = await sidecar(root, path.join(group.directory, stem + '.report.json'));
        const source = questions.value?.source_export;
        const classification=formFeatures(questions.value,report.value);
        for (const field of ['features','answerTypes','compiledKinds']) form[field]=[...new Set([...form[field],...classification[field]])].sort();
        form.name = source?.content?.name?.trim() || form.name;
        form.formId = String(questions.value?.form_id ?? report.value?.form_id ?? form.formId);
        form.questionCount = source?.content?.steps?.length ?? report.value?.question_count ?? form.questionCount;
        const variant = { id: key(file.name), filename: file.name, mode: report.value?.mode || (/(^|\.)flat$/.test(stem) ? 'flat' : /(^|\.)auto$/.test(stem) ? 'auto' : 'diagram'), groups: report.value?.decomposition?.length ?? null, issues: [questions.issue, report.issue].filter(Boolean) };
        form.variants.push(variant);
        lookup.set(form.id + '/' + variant.id, { directory: group.directory, file: file.name });
      }
      if (!files.length) form.features.push('failed');
      // A missing sidecar on one variant must not override known source data.
      if (form.answerTypes.length) form.features=form.features.filter(f=>f!=='unknown');
      form.issues = form.variants.flatMap(v => v.issues);
      if (log && /UNSUPPORTED:|Traceback \(most recent call last\)/.test(log)) form.issues.push('Latest conversion log reports failure; existing diagrams may be stale.');
      if (!files.length) form.issues.push('No BPMN generated; inspect the conversion log.');
      forms.push(form);
    }
    forms.sort((a,b) => a.formId.localeCompare(b.formId, undefined, { numeric:true }));
    return { forms, lookup, notice: null, directory: root };
  }
  async function getIndex(refresh = false) {
    if (refresh) index = null;
    if (!index) {
      scanning ||= scan().then(value => { index = value; return value; }).finally(() => { scanning = null; });
      await scanning;
    }
    return index;
  }
  return {
    async list(refresh = false) { const { lookup, ...publicIndex } = await getIndex(refresh); return publicIndex; },
    async load(formId, variantId) {
      const item = (await getIndex()).lookup.get(formId + '/' + variantId);
      if (!item) return null;
      const filename = path.join(item.directory, item.file), stem = filename.slice(0, -5);
      const [xml, questions, report] = await Promise.all([safeRead(root, filename), sidecar(root, stem + '.questions.json'), sidecar(root, stem + '.report.json')]);
      return { xml, filename: item.file, questions: questions.value, report: report.value, issues: [questions.issue, report.issue].filter(Boolean) };
    },
    async log(formId) {
      const form = (await getIndex()).forms.find(f => f.id === formId);
      if (!form) return null;
      try { return await safeRead(root, path.join(form.folder === '(root)' ? root : path.join(root, form.folder), 'conversion.log')); }
      catch { return ''; }
    }
  };
}

const mime = { '.html':'text/html; charset=utf-8', '.css':'text/css; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.woff':'font/woff', '.woff2':'font/woff2', '.ttf':'font/ttf' };
export function createServer(rootDirectory) {
  const catalogue = createCatalogue(rootDirectory);
  return http.createServer(async (request, response) => {
    response.setHeader('Cache-Control', 'no-store');
    response.setHeader('X-Content-Type-Options', 'nosniff');
    // Same-origin local application, no external assets or arbitrary sidecar URLs.
    response.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'");
    function json(code, value) { response.writeHead(code, { 'Content-Type':'application/json; charset=utf-8' }); response.end(JSON.stringify(value)); }
    if (request.method !== 'GET') return json(405, { error:'Read-only viewer: only GET requests are supported' });
    try {
      const url = new URL(request.url, 'http://localhost');
      if (url.pathname === '/api/forms') return json(200, await catalogue.list(url.searchParams.get('refresh') === '1'));
      const diagram = /^\/api\/forms\/([A-Za-z0-9_-]+)\/variants\/([A-Za-z0-9_-]+)$/.exec(url.pathname);
      if (diagram) { const data = await catalogue.load(diagram[1], diagram[2]); return json(data ? 200 : 404, data || { error:'Unknown form or diagram; refresh the catalogue' }); }
      const log = /^\/api\/forms\/([A-Za-z0-9_-]+)\/log$/.exec(url.pathname);
      if (log) { const value = await catalogue.log(log[1]); return json(value === null ? 404 : 200, value === null ? { error:'Unknown form' } : { log:value }); }
      let filename;
      if (url.pathname === '/') filename = path.join(publicDirectory, 'index.html');
      else if (['/app.js','/style.css','/metadata.js','/viewport.js','/overview.js','/typography.js','/regions.js'].includes(url.pathname)) filename = path.join(publicDirectory, url.pathname.slice(1));
      else if (url.pathname === '/vendor/bpmn.js') filename = path.join(vendorDirectory, 'bpmn-navigated-viewer.production.min.js');
      else if (url.pathname.startsWith('/vendor/assets/')) {
        const relative = decodeURIComponent(url.pathname.slice('/vendor/'.length));
        filename = path.resolve(vendorDirectory, relative);
        if (!contained(path.join(vendorDirectory, 'assets'), filename)) return json(404,{error:'Not found'});
      } else return json(404,{error:'Not found'});
      const bytes = await fs.readFile(filename);
      response.writeHead(200, { 'Content-Type':mime[path.extname(filename)] || 'application/octet-stream' });
      response.end(bytes);
    } catch (error) { json(error.code === 'ENOENT' ? 404 : 500, { error:error.message }); }
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  function option(name, fallback) { const i = args.indexOf(name); return i >= 0 ? args[i+1] : fallback; }
  const root = path.resolve(option('--dir', path.join(appDirectory, '../bpmn_forms')));
  const port = Number(option('--port', '5178'));
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid --port');
  const server = createServer(root);
  server.on('error', error => { console.error(error.message); process.exitCode = 1; });
  server.listen(port, '127.0.0.1', () => console.log(`Forms BPMN viewer: http://127.0.0.1:${port}\nReading: ${root}\nRefresh catalogue after converting more forms.`));
}
