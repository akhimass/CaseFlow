const CONSENT_KEY = 'caseflow_consent';
const CASE_ID_KEY = 'caseflow_case_id';

export type ConsentRecord = {
  consent_given_at: string;
  case_id: string;
  caller_location?: string;
};

export function getConsentRecord(): ConsentRecord | null {
  if (typeof window === 'undefined') return null;
  const raw = sessionStorage.getItem(CONSENT_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ConsentRecord;
  } catch {
    return null;
  }
}

export function setConsentRecord(record: ConsentRecord) {
  sessionStorage.setItem(CONSENT_KEY, JSON.stringify(record));
  sessionStorage.setItem(CASE_ID_KEY, record.case_id);
}

export function hasCallerLocation(): boolean {
  return Boolean(getConsentRecord()?.caller_location?.trim());
}

export function getCaseIdFromSession(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem(CASE_ID_KEY);
}

export function buildAgentMetadata(): Record<string, string> {
  const consent = getConsentRecord();
  if (!consent) return {};
  const metadata: Record<string, string> = {
    case_id: consent.case_id,
    consent_given_at: consent.consent_given_at,
  };
  if (consent.caller_location) {
    metadata.caller_location = consent.caller_location;
  }
  return metadata;
}
