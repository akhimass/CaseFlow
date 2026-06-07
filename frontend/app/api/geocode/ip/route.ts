import { NextResponse } from 'next/server';

// IP-based geolocation fallback for "Use my location" when the browser's GPS
// lookup is denied, times out, or is unavailable (common on desktop). Resolves
// the caller's city server-side from their IP.
//
// Local dev note: when there's no forwarded client IP (localhost), we query the
// provider WITHOUT an IP, which geolocates the server's egress IP — i.e. your
// own network — so it still returns a sensible city during development. In
// production the forwarded client IP is used.

function isPrivateOrLocal(ip: string): boolean {
  if (!ip) return true;
  if (ip === '::1' || ip.startsWith('127.') || ip.toLowerCase() === 'localhost') return true;
  if (ip.startsWith('10.') || ip.startsWith('192.168.')) return true;
  const m = ip.match(/^172\.(\d+)\./);
  if (m) {
    const second = Number(m[1]);
    if (second >= 16 && second <= 31) return true;
  }
  return false;
}

function clientIp(request: Request): string {
  const fwd = request.headers.get('x-forwarded-for');
  if (fwd) {
    const first = fwd.split(',')[0]?.trim();
    if (first) return first;
  }
  return request.headers.get('x-real-ip')?.trim() ?? '';
}

export async function GET(request: Request) {
  try {
    const ip = clientIp(request);
    const target = isPrivateOrLocal(ip) ? '' : ip;
    const url = `http://ip-api.com/json/${target}?fields=status,city,region,regionName,country`;

    const res = await fetch(url, {
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(6000),
    });
    if (!res.ok) return NextResponse.json({ label: null }, { status: 200 });

    const data = (await res.json()) as {
      status?: string;
      city?: string;
      region?: string; // short code, e.g. "CA"
      regionName?: string;
    };

    if (data.status !== 'success' || !data.city) {
      return NextResponse.json({ label: null }, { status: 200 });
    }

    const state = data.region || data.regionName;
    const label = state ? `${data.city}, ${state}` : data.city;
    return NextResponse.json({ label }, { status: 200 });
  } catch {
    return NextResponse.json({ label: null }, { status: 200 });
  }
}
