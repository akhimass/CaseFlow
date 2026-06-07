import { NextResponse } from 'next/server';

// Reverse-geocode lat/lon → "City, ST" on the server. Doing this server-side
// (instead of calling Nominatim from the browser) avoids CORS surprises, lets us
// send the descriptive User-Agent Nominatim's usage policy requires, and keeps
// the third-party dependency off the client.

const US_STATES: Record<string, string> = {
  alabama: 'AL',
  alaska: 'AK',
  arizona: 'AZ',
  arkansas: 'AR',
  california: 'CA',
  colorado: 'CO',
  connecticut: 'CT',
  delaware: 'DE',
  florida: 'FL',
  georgia: 'GA',
  hawaii: 'HI',
  idaho: 'ID',
  illinois: 'IL',
  indiana: 'IN',
  iowa: 'IA',
  kansas: 'KS',
  kentucky: 'KY',
  louisiana: 'LA',
  maine: 'ME',
  maryland: 'MD',
  massachusetts: 'MA',
  michigan: 'MI',
  minnesota: 'MN',
  mississippi: 'MS',
  missouri: 'MO',
  montana: 'MT',
  nebraska: 'NE',
  nevada: 'NV',
  'new hampshire': 'NH',
  'new jersey': 'NJ',
  'new mexico': 'NM',
  'new york': 'NY',
  'north carolina': 'NC',
  'north dakota': 'ND',
  ohio: 'OH',
  oklahoma: 'OK',
  oregon: 'OR',
  pennsylvania: 'PA',
  'rhode island': 'RI',
  'south carolina': 'SC',
  'south dakota': 'SD',
  tennessee: 'TN',
  texas: 'TX',
  utah: 'UT',
  vermont: 'VT',
  virginia: 'VA',
  washington: 'WA',
  'west virginia': 'WV',
  wisconsin: 'WI',
  wyoming: 'WY',
  'district of columbia': 'DC',
};

function abbreviateState(state: string | undefined): string | undefined {
  if (!state) return undefined;
  const code = US_STATES[state.trim().toLowerCase()];
  return code ?? state;
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const lat = searchParams.get('lat');
  const lon = searchParams.get('lon');

  if (!lat || !lon || Number.isNaN(Number(lat)) || Number.isNaN(Number(lon))) {
    return NextResponse.json({ error: 'invalid_coordinates' }, { status: 400 });
  }

  try {
    const url = `https://nominatim.openstreetmap.org/reverse?lat=${encodeURIComponent(
      lat
    )}&lon=${encodeURIComponent(lon)}&format=json&zoom=10&addressdetails=1`;

    const res = await fetch(url, {
      headers: {
        Accept: 'application/json',
        // Nominatim's usage policy requires a descriptive User-Agent.
        'User-Agent': 'Caseflowy/1.0 (intake location lookup; support@caseflowy.com)',
      },
      // Don't let a slow third party hang the request.
      signal: AbortSignal.timeout(7000),
    });

    if (!res.ok) {
      return NextResponse.json({ label: null }, { status: 200 });
    }

    const data = (await res.json()) as {
      address?: {
        city?: string;
        town?: string;
        village?: string;
        hamlet?: string;
        municipality?: string;
        county?: string;
        state?: string;
      };
    };

    const a = data.address ?? {};
    const city = a.city ?? a.town ?? a.village ?? a.hamlet ?? a.municipality ?? a.county;
    const state = abbreviateState(a.state);

    const label = city && state ? `${city}, ${state}` : (city ?? null);
    return NextResponse.json({ label }, { status: 200 });
  } catch {
    return NextResponse.json({ label: null }, { status: 200 });
  }
}
