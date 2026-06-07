import {
  BarChart3,
  Camera,
  Check,
  FileText,
  FlaskConical,
  Globe,
  Scale,
  Shield,
} from 'lucide-react';

export const STATS = [
  { value: 'ES + EN', label: 'Your language, your story' },
  { value: 'Live', label: 'Show documents on camera' },
  { value: '~15 min', label: 'Typical case review' },
  { value: 'Free', label: 'No cost to get started' },
] as const;

export const FEATURES = [
  {
    icon: Globe,
    title: 'Spanish or English',
    body: 'Tell us what happened in the language you are most comfortable with — your intake specialist stays with you for the whole conversation.',
  },
  {
    icon: Check,
    title: 'Instant qualification',
    body: 'Confirms injury, treatment, fault, and representation — then scores the case before it reaches your team.',
  },
  {
    icon: Camera,
    title: 'Live document parsing',
    body: 'Callers hold police reports and ER discharges to camera; Unsiloed parses fields while the firm dashboard updates.',
  },
  {
    icon: FlaskConical,
    title: 'Moss legal retrieval',
    body: 'SoL rules, comparable settlements, and firm profiles retrieved in parallel during intake.',
  },
  {
    icon: Scale,
    title: 'Discrepancy detection',
    body: 'Catches conflicts between verbal accounts and parsed documents — and asks clarifying questions gently.',
  },
  {
    icon: FileText,
    title: 'Firm dashboard',
    body: 'Live case files with transcripts, parsed docs, comparables, strength score, and match results.',
  },
] as const;

export const FEATURE_HIGHLIGHTS = [
  {
    icon: BarChart3,
    title: 'Case strength scoring',
    body: 'Liability clarity, injury documentation, jurisdiction, and SoL validity roll into a 0–100 score in real time.',
  },
  {
    icon: Shield,
    title: 'Built for legal compliance',
    body: 'No legal advice, full transcripts, audit trails, and firm-side review before any outbound contact.',
  },
] as const;

export const MOCK_ROWS = [
  {
    caller: 'Caller · (570) 332-2862',
    type: 'Auto accident',
    disposition: 'Qualified',
    score: '92',
    caseValue: '$186K',
    summary: 'intake-570332.pdf',
    ok: true,
  },
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
  {
    caller: 'Carlos Mendoza',
    type: 'Auto · ES',
    disposition: 'Qualified',
    score: '94',
    caseValue: '$310K',
    summary: 'intake-mendoza.pdf',
    ok: true,
  },
] as const;

export const CTA_NOTE =
  'Injured in a car crash, slip and fall, or workplace accident? Start your case on live video — our specialist guides you step by step and helps connect you with a firm that fits.';
