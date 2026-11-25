// Ports of durable_poc/src/paths.py and src/actions.py — kept behaviourally
// identical so mocked runs branch the same way the Temporal interpreter does.

type Ctx = Record<string, unknown>;

const DURATION_RE =
  /^P(?=.)(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$/;

function isDigits(part: string): boolean {
  return /^\d+$/.test(part);
}

function isPlainObject(value: unknown): value is Ctx {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function resolvePath(context: unknown, path: string | null | undefined): unknown {
  if (!path) return null;
  let current: unknown = context;
  for (const part of path.split('.')) {
    if (isPlainObject(current) && part in current) {
      current = current[part];
    } else if (Array.isArray(current) && isDigits(part)) {
      const idx = Number(part);
      if (idx < 0 || idx >= current.length) return null;
      current = current[idx];
    } else {
      return null;
    }
  }
  return current ?? null;
}

export function setPath(context: Ctx, path: string, value: unknown): void {
  const parts = path.split('.');
  let current: unknown = context;
  for (let i = 0; i < parts.length - 1; i++) {
    const part = parts[i];
    const nextPart = parts[i + 1];
    if (isPlainObject(current)) {
      if (!(part in current)) current[part] = isDigits(nextPart) ? [] : {};
      current = current[part];
    } else if (Array.isArray(current) && isDigits(part)) {
      const idx = Number(part);
      while (current.length <= idx) current.push({});
      current = current[idx];
    }
  }
  const last = parts[parts.length - 1];
  if (isPlainObject(current)) {
    current[last] = value;
  } else if (Array.isArray(current) && isDigits(last)) {
    const idx = Number(last);
    while (current.length <= idx) current.push(null);
    current[idx] = value;
  }
}

// Python's str() of a value, so interpolated prompts read the same as they do
// against the real executor ("True", "['a', 'b']", "{'k': 'v'}").
export function pyStr(value: unknown): string {
  if (value === null || value === undefined) return 'None';
  if (value === true) return 'True';
  if (value === false) return 'False';
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return String(value);
  return pyRepr(value);
}

function pyRepr(value: unknown): string {
  if (typeof value === 'string') return `'${value.replace(/\\/g, '\\\\').replace(/'/g, "\\'")}'`;
  if (Array.isArray(value)) return `[${value.map(pyRepr).join(', ')}]`;
  if (isPlainObject(value)) {
    return `{${Object.entries(value)
      .map(([k, v]) => `${pyRepr(k)}: ${pyRepr(v)}`)
      .join(', ')}}`;
  }
  return pyStr(value);
}

export function interpolate(template: string, context: Ctx): string {
  return template.replace(/\{\{(.*?)\}\}/g, (_match, path: string) => {
    const val = resolvePath(context, path.trim());
    return val === null ? '' : pyStr(val);
  });
}

export function resolveDict(data: unknown, context: Ctx): unknown {
  if (isPlainObject(data)) {
    const keys = Object.keys(data);
    if (keys.length === 1 && keys[0] === '$') {
      return resolvePath(context, data.$ as string);
    }
    return Object.fromEntries(Object.entries(data).map(([k, v]) => [k, resolveDict(v, context)]));
  }
  if (Array.isArray(data)) {
    return data.map((item) => resolveDict(item, context));
  }
  return data;
}

/** ISO 8601 duration → milliseconds. Throws like `parse_duration` on bad input. */
export function parseDuration(durationStr: string): number {
  const match = durationStr && durationStr !== 'P' ? DURATION_RE.exec(durationStr) : null;
  if (!match) throw new Error(`Invalid duration format: '${durationStr}'`);
  const [, days = '0', hours = '0', minutes = '0', seconds = '0'] = match;
  const ms =
    ((Number(days) * 24 + Number(hours)) * 60 + Number(minutes)) * 60_000 + Number(seconds) * 1000;
  if (ms === 0) throw new Error(`Duration string '${durationStr}' resolved to 0 time`);
  return ms;
}

// Naive (timezone-less) datetimes, as Python's strptime produces — held as
// UTC Dates so arithmetic never shifts across DST.
const DATE_FORMATS: Array<[RegExp, (m: RegExpExecArray) => number[]]> = [
  [/^(\d{4})-(\d{2})-(\d{2})$/, (m) => [+m[1], +m[2], +m[3]]],
  [/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})$/, (m) => [+m[1], +m[2], +m[3], +m[4], +m[5], +m[6]]],
  [/^(\d{2})\/(\d{2})\/(\d{4})$/, (m) => [+m[3], +m[2], +m[1]]],
  [/^(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2}):(\d{2})$/, (m) => [+m[3], +m[2], +m[1], +m[4], +m[5], +m[6]]]
];

export function parseDate(val: unknown): Date | null {
  if (!val) return null;
  if (val instanceof Date) return val;
  const valStr = String(val).trim().split('.')[0];
  for (const [re, parts] of DATE_FORMATS) {
    const m = re.exec(valStr);
    if (!m) continue;
    const [y, mo, d, h = 0, mi = 0, s = 0] = parts(m);
    const date = new Date(Date.UTC(y, mo - 1, d, h, mi, s));
    // Reject rollovers like 31/02 that strptime would refuse.
    if (date.getUTCMonth() !== mo - 1 || date.getUTCDate() !== d) return null;
    return date;
  }
  return null;
}

/** A naive-UTC Date as Python's `datetime.isoformat()` would render it. */
export function isoNaive(date: Date): string {
  return date.toISOString().replace('Z', '+00:00');
}

function pad(n: number): string {
  return String(n).padStart(2, '0');
}

export function applyDateMath(dateVal: unknown, offsetStr: unknown, opType: 'add' | 'subtract'): string | null {
  if (!dateVal || !offsetStr) return null;
  const valStr = String(dateVal).trim();
  const dt = parseDate(valStr);
  if (!dt) return null;

  const match = /(\d+)\s*(week|day|month|year)/.exec(String(offsetStr).toLowerCase());
  if (!match) return null;
  const amount = Number(match[1]) * (opType === 'add' ? 1 : -1);
  const unit = match[2];

  const res = new Date(dt);
  if (unit === 'week') res.setUTCDate(res.getUTCDate() + amount * 7);
  else if (unit === 'day') res.setUTCDate(res.getUTCDate() + amount);
  else if (unit === 'month') {
    const target = new Date(Date.UTC(dt.getUTCFullYear(), dt.getUTCMonth() + amount, 1));
    const lastDay = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
    res.setTime(Date.UTC(target.getUTCFullYear(), target.getUTCMonth(), Math.min(dt.getUTCDate(), lastDay)));
  } else if (unit === 'year') res.setUTCFullYear(res.getUTCFullYear() + amount);

  const [y, m, d] = [res.getUTCFullYear(), pad(res.getUTCMonth() + 1), pad(res.getUTCDate())];
  return valStr.includes('/') ? `${d}/${m}/${y}` : `${y}-${m}-${d}`;
}
