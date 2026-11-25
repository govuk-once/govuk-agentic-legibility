import type { RunStateDTO } from '$lib/types';

// Port of durable_poc/agent/agent.py:_coerce_value and its _TRUTHY set.
const TRUTHY = new Set(['true', 'yes', 'y', 'yeah', 'sure', 'confirm', '1']);

export function coerceValue(value: unknown, sessionState: RunStateDTO | null): unknown {
  if (typeof value === 'string' && ['true', 'false'].includes(value.trim().toLowerCase())) {
    return value.trim().toLowerCase() === 'true';
  }

  if (!sessionState) {
    return value;
  }

  const awaiting = sessionState.awaiting;
  if (!awaiting) {
    return value;
  }

  const schema = (awaiting.schema ?? {}) as unknown as Record<string, unknown>;
  const kind = schema.kind;

  if (kind === 'boolean') {
    if (typeof value === 'boolean') {
      return value;
    }
    return TRUTHY.has(String(value).trim().toLowerCase());
  }

  if (kind === 'string') {
    let valStr = String(value).trim();
    if (
      (valStr.startsWith('"') && valStr.endsWith('"')) ||
      (valStr.startsWith("'") && valStr.endsWith("'"))
    ) {
      valStr = valStr.slice(1, -1);
    }
    return valStr;
  }

  if (kind === 'select_one') {
    if (typeof value === 'string' && value.trim().startsWith('{')) {
      try {
        return JSON.parse(value);
      } catch {
        // fall through to option matching
      }
    }

    const rawOptions =
      (awaiting as unknown as { options?: unknown }).options ?? schema.options ?? [];
    if (Array.isArray(rawOptions)) {
      const needle = String(value).trim().toLowerCase();
      const valueKey = typeof schema.value_key === 'string' ? schema.value_key : undefined;
      // interpreter.py expands a select_one into the whole option (e.g. a full
      // address for value_key "uprn") only when given its 1-based index, so
      // answer with the index for those keys; a bare uprn would be stored as-is.
      const wantsIndex = ['uprn', 'single_line', 'address_line_1'].includes(valueKey ?? '');
      if (wantsIndex && /^\d+$/.test(needle) && Number(needle) >= 1 && Number(needle) <= rawOptions.length) {
        return Number(needle);
      }
      for (const [index, opt] of rawOptions.entries()) {
        if (opt && typeof opt === 'object') {
          const o = opt as Record<string, unknown>;
          const optVal = (valueKey && o[valueKey]) ?? o.value ?? o.id;
          const optLbl = o.label ?? o.title ?? o.single_line;
          if (
            needle === String(optVal).trim().toLowerCase() ||
            needle === String(optLbl).trim().toLowerCase()
          ) {
            return wantsIndex ? index + 1 : (optVal ?? opt);
          }
        } else if (needle === String(opt).trim().toLowerCase()) {
          return opt;
        }
      }
    }

    return value != null ? String(value).trim() : value;
  }

  if (kind === 'select_many') {
    if (typeof value === 'string') {
      const trimmed = value.trim();
      if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
        try {
          return JSON.parse(trimmed);
        } catch {
          // fall through to comma-splitting
        }
      }
      return trimmed
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean);
    }
    return value;
  }

  if (kind === 'file_ref' || (typeof value === 'string' && value.includes('bytes'))) {
    const wfId = sessionState.workflow_id ?? 'file';

    if (typeof value === 'string' && value.trim().startsWith('{')) {
      try {
        value = JSON.parse(value);
      } catch {
        // leave as the original string
      }
    }

    if (typeof value === 'string' && value.startsWith('[Uploaded File:')) {
      const refMatch = value.match(/ref='([^']+)'/);
      const ctMatch = value.match(/content_type='([^']+)'/);
      const bytesMatch = value.match(/bytes=(\d+)/);
      return {
        ref: refMatch ? refMatch[1] : `upload_${wfId}.dat`,
        content_type: ctMatch ? ctMatch[1] : 'image/jpeg',
        bytes: bytesMatch ? parseInt(bytesMatch[1], 10) : 1024
      };
    }

    if (value && typeof value === 'object' && Number((value as Record<string, unknown>).bytes ?? 0) > 0) {
      const v = value as Record<string, unknown>;
      return {
        ref: String(v.ref ?? `upload_${wfId}.dat`),
        content_type: String(v.content_type ?? 'image/jpeg'),
        bytes: Number(v.bytes ?? 1024)
      };
    }

    return { error: 'INVALID_FILE_UPLOAD' };
  }

  return value;
}
