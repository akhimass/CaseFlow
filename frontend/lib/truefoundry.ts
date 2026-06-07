export { gatewayChat, gatewayConfigured, type GatewayMetadata } from '@/lib/gateway';

/** @deprecated Prefer gatewayChat from @/lib/gateway */
export async function gatewayFetch(path: string, body: unknown): Promise<Response> {
  const base = (process.env.TRUEFOUNDRY_GATEWAY_URL ?? '').replace(/\/$/, '');
  if (!base) {
    throw new Error('TRUEFOUNDRY_GATEWAY_URL is not configured');
  }
  const apiKey = process.env.TRUEFOUNDRY_API_KEY;
  return fetch(`${base}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
    },
    body: JSON.stringify(body),
  });
}
