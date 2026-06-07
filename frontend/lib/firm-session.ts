export const FIRM_SESSION_COOKIE = 'caseflow_firm_session';

export type FirmSession = {
  firm_id: string;
  firm_name: string;
  city?: string;
};

export function parseFirmSessionCookie(raw: string | undefined): FirmSession | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as FirmSession;
    if (!parsed.firm_id || !parsed.firm_name) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function caseVisibleToFirm(record: Record<string, unknown>, firmId: string): boolean {
  if (!firmId) return false;
  if (record.matched_firm_id === firmId) return true;
  const matches = (record.matches as Array<{ firm_id?: string }> | undefined) ?? [];
  return matches.some((match) => match.firm_id === firmId);
}
