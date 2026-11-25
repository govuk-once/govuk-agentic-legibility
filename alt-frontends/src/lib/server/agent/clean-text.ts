// Port of durable_poc/agent/api/events.py:clean_text_pipes.
export function cleanTextPipes(text: string): string {
  if (!text) return '';
  const lines = text.split('\n').map((line) => line.replace(/^\s*\|\s*|\s*\|\s*$/g, ''));
  return lines.join('\n').trim();
}
