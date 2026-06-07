export type MossNamespace = 'state-law' | 'settlements' | 'firms' | 'procedures';

export type MossResult = {
  text: string;
  score?: number;
  metadata?: Record<string, string>;
};

export async function retrieve(query: string, namespace: MossNamespace): Promise<MossResult[]> {
  const res = await fetch('/api/moss/retrieve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, namespace }),
  });
  if (!res.ok) {
    throw new Error(`Moss retrieve failed: ${res.status}`);
  }
  const data = (await res.json()) as { matches?: MossResult[] };
  return data.matches ?? [];
}
