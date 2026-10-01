import { parseDate, resolvePath } from './paths';

// Port of durable_poc/src/predicates.py:evaluate.

type Ctx = Record<string, unknown>;
type Condition = Record<string, unknown>;

function resolveValue(condition: Condition, context: Ctx): unknown {
  if ('value' in condition) return condition.value;
  if ('value_path' in condition) return resolvePath(context, condition.value_path as string);
  return null;
}

// Python truthiness: empty containers are falsy.
export function pyTruthy(val: unknown): boolean {
  if (Array.isArray(val)) return val.length > 0;
  if (typeof val === 'object' && val !== null) return Object.keys(val).length > 0;
  return Boolean(val);
}

function toNumber(val: unknown): number | null {
  if (typeof val === 'boolean') return val ? 1 : 0;
  if (typeof val === 'string' && val.trim() === '') return null;
  const n = Number(val);
  return Number.isNaN(n) ? null : n;
}

export function evaluate(condition: Condition, context: Ctx): boolean {
  const op = condition.op as string | undefined;
  if (!op) throw new Error("Condition missing 'op' key.");
  const pathVal = () => resolvePath(context, condition.path as string);

  switch (op) {
    case 'eq':
    case 'equals': {
      const p = pathVal();
      const c = resolveValue(condition, context);
      if (p === null || c === null) return p === c;
      if (typeof p === typeof c && (typeof p !== 'object' || Array.isArray(p) === Array.isArray(c))) {
        return typeof p === 'object' ? JSON.stringify(p) === JSON.stringify(c) : p === c;
      }
      return String(p).trim().toLowerCase() === String(c).trim().toLowerCase();
    }
    case 'lt':
    case 'lte':
    case 'less_than':
    case 'less_than_or_equal':
    case 'gt':
    case 'gte':
    case 'greater_than':
    case 'greater_than_or_equal': {
      const p = toNumber(pathVal());
      const c = toNumber(resolveValue(condition, context));
      if (p === null || c === null) return false;
      if (op === 'lt' || op === 'less_than') return p < c;
      if (op === 'lte' || op === 'less_than_or_equal') return p <= c;
      if (op === 'gt' || op === 'greater_than') return p > c;
      return p >= c;
    }
    case 'is_true': {
      const val = pathVal();
      if (typeof val === 'boolean') return val;
      if (typeof val === 'string') return ['true', 'y', 'yes', '1'].includes(val.trim().toLowerCase());
      return pyTruthy(val);
    }
    case 'is_false': {
      const val = pathVal();
      if (typeof val === 'boolean') return !val;
      if (typeof val === 'string') return ['false', 'n', 'no', '0'].includes(val.trim().toLowerCase());
      return false;
    }
    case 'not_empty': {
      const val = pathVal();
      return pyTruthy(val) && val !== '';
    }
    case 'and':
      return ((condition.all ?? condition.rules ?? []) as Condition[]).every((sub) => evaluate(sub, context));
    case 'or':
      return ((condition.any ?? condition.rules ?? []) as Condition[]).some((sub) => evaluate(sub, context));
    case 'not': {
      const sub = (condition.condition ?? condition.rule) as Condition | undefined;
      if (!sub) throw new Error("Operator 'not' requires a 'condition' or 'rule' key.");
      return !evaluate(sub, context);
    }
    case 'date_before': {
      const d1 = parseDate(resolvePath(context, (condition.path as string) ?? '') ?? resolvePath(context, '__now__'));
      const d2 = parseDate(resolveValue(condition, context));
      if (!d1 || !d2) return false;
      return d1 < d2;
    }
    case 'before_now': {
      const nowTs = resolvePath(context, '__now__');
      if (!nowTs) throw new Error("Runtime context missing deterministic '__now__' key");
      const now = parseDate(nowTs);
      const target = parseDate(pathVal());
      if (!now || !target) return false;
      return target < now;
    }
    case 'date_diff_greater_than': {
      const target = parseDate(pathVal());
      const now = parseDate(resolvePath(context, '__now__'));
      if (!target || !now) return false;
      const diffDays = Math.floor(Math.abs(now.getTime() - target.getTime()) / 86_400_000);
      const valStr = String(condition.value ?? '').toLowerCase();
      const num = Number(/\d+/.exec(valStr)?.[0] ?? 1);
      if (valStr.includes('month')) return diffDays > num * 30;
      if (valStr.includes('week')) return diffDays > num * 7;
      if (valStr.includes('day')) return diffDays > num;
      return false;
    }
    case 'contains':
    case 'in':
    case 'includes': {
      const p = pathVal();
      const c = resolveValue(condition, context);
      if (p === null || c === null) return false;
      const needle = String(c).trim().toLowerCase();
      if (Array.isArray(p)) return p.some((item) => String(item).trim().toLowerCase() === needle);
      return String(p).trim().toLowerCase().includes(needle);
    }
  }
  throw new Error(`Unrecognised operator: ${op}`);
}
