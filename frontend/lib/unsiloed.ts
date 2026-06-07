export type DocType = 'police_report' | 'er_discharge' | 'insurance';

export type ParsedFields = Record<string, string | number | boolean | null>;

export async function parseDoc(imageBase64: string, docType: DocType): Promise<ParsedFields> {
  const res = await fetch('/api/unsiloed/parse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ imageBase64, docType }),
  });
  if (!res.ok) {
    throw new Error(`Unsiloed parse failed: ${res.status}`);
  }
  return (await res.json()) as ParsedFields;
}
