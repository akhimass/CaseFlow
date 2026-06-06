export const STATS = [
  { value: 'ES + EN', label: 'Bilingual intake' },
  { value: 'Live', label: 'Document parsing' },
  { value: '3', label: 'Firm matches per case' },
  { value: '90s', label: 'Demo-ready flow' },
] as const;

export const FEATURES = [
  {
    title: 'Video intake in your language',
    body: 'Aria detects Spanish or English and runs the full intake without switching mid-call.',
  },
  {
    title: 'Live document parsing',
    body: 'Police reports and ER discharges parsed via Unsiloed while the caller holds them to camera.',
  },
  {
    title: 'Moss legal retrieval',
    body: 'SoL rules, comparable settlements, and firm profiles retrieved in parallel during intake.',
  },
] as const;

export const MOCK_ROWS = [
  {
    caller: 'Maria Delgado',
    type: 'Auto · ES',
    disposition: 'Qualified',
    score: '78',
    caseValue: '$45–72K',
    summary: 'intake-delgado.pdf',
    ok: true,
  },
  {
    caller: 'James Okafor',
    type: 'Slip & fall',
    disposition: 'Qualified',
    score: '91',
    caseValue: '$92K',
    summary: 'intake-okafor.pdf',
    ok: true,
  },
  {
    caller: 'Priya Nair',
    type: 'Auto accident',
    disposition: 'Declined',
    score: '28',
    caseValue: '—',
    summary: '—',
    ok: false,
  },
] as const;
