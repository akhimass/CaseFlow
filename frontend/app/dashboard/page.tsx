import { readFile } from 'node:fs/promises';
import path from 'node:path';

async function readDashboardHtml() {
  const candidatePaths = [
    path.resolve(process.cwd(), '..', 'index (1).html'),
    path.resolve(process.cwd(), 'index (1).html'),
  ];

  for (const filePath of candidatePaths) {
    try {
      return await readFile(filePath, 'utf8');
    } catch {
      // Try the next candidate path.
    }
  }

  throw new Error('Unable to locate index (1).html for the dashboard route.');
}

export default async function DashboardPage() {
  const html = await readDashboardHtml();

  return (
    <main className="min-h-svh bg-background">
      <iframe
        title="Caseflow dashboard"
        className="h-svh w-full border-0"
        srcDoc={html}
      />
    </main>
  );
}
