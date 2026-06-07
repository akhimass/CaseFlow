import { NextResponse } from 'next/server';

const VOICE_OPTIONS = {
  es: [
    'Spanish_SereneWoman',
    'Spanish_Soft-spokenGirl',
    'Spanish_Kind-heartedGirl',
    'Spanish_Narrator',
    'Spanish_ThoughtfulLady',
  ],
  en: [
    'voice_agent_Female_Phone_4',
    'English_SereneWoman',
    'English_Kind-heartedGirl',
    'English_Friendly_Female_3',
    'English_Steady_Female_1',
  ],
} as const;

const EMOTIONS = [
  'neutral',
  'calm',
  'happy',
  'sad',
  'angry',
  'fearful',
  'disgusted',
  'surprised',
  'fluent',
] as const;

type PreviewBody = {
  text?: string;
  voiceId?: string;
  language?: 'es' | 'en';
  speed?: number;
  volume?: number;
  pitch?: number;
  emotion?: string;
  model?: string;
};

export async function POST(req: Request) {
  if (process.env.NODE_ENV === 'production') {
    return NextResponse.json({ error: 'Not available in production' }, { status: 404 });
  }

  const apiKey = process.env.MINIMAX_API_KEY;
  if (!apiKey) {
    return NextResponse.json({ error: 'MINIMAX_API_KEY is not configured' }, { status: 500 });
  }

  let body: PreviewBody;
  try {
    body = (await req.json()) as PreviewBody;
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const language = body.language === 'en' ? 'en' : 'es';
  const voiceId =
    body.voiceId ??
    (language === 'es' ? process.env.MINIMAX_VOICE_ID_ES : process.env.MINIMAX_VOICE_ID_EN) ??
    (language === 'es' ? VOICE_OPTIONS.es[0] : VOICE_OPTIONS.en[0]);

  const text =
    body.text?.trim() ||
    (language === 'es'
      ? 'Hola, soy Aria. Cuéntame qué pasó.'
      : 'Hi, I am Aria. Tell me what happened.');

  const payload = {
    model: body.model || process.env.MINIMAX_TTS_MODEL || 'speech-2.8-hd',
    text,
    stream: false,
    language_boost: language === 'es' ? 'Spanish' : 'English',
    output_format: 'hex',
    voice_setting: {
      voice_id: voiceId,
      speed: body.speed ?? Number(process.env.MINIMAX_SPEED ?? 1),
      vol: body.volume ?? Number(process.env.MINIMAX_VOLUME ?? 1),
      pitch: body.pitch ?? Number(process.env.MINIMAX_PITCH ?? 0),
      emotion: body.emotion ?? process.env.MINIMAX_EMOTION ?? 'neutral',
    },
    audio_setting: {
      sample_rate: 24000,
      bitrate: 128000,
      format: 'mp3',
      channel: 1,
    },
  };

  const baseUrl = process.env.MINIMAX_BASE_URL || 'https://api.minimax.io';
  const started = Date.now();

  const upstream = await fetch(`${baseUrl}/v1/t2a_v2`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  const raw = await upstream.text();
  if (!upstream.ok) {
    return NextResponse.json(
      { error: 'MiniMax TTS request failed', status: upstream.status, detail: raw.slice(0, 500) },
      { status: 502 }
    );
  }

  let parsed: {
    data?: { audio?: string; status?: number };
    base_resp?: { status_code?: number; status_msg?: string };
    extra_info?: { audio_length?: number };
  };
  try {
    parsed = JSON.parse(raw) as typeof parsed;
  } catch {
    return NextResponse.json({ error: 'Invalid MiniMax response' }, { status: 502 });
  }

  const statusCode = parsed.base_resp?.status_code ?? 0;
  if (statusCode !== 0) {
    return NextResponse.json(
      {
        error: parsed.base_resp?.status_msg || 'MiniMax TTS error',
        status_code: statusCode,
      },
      { status: 502 }
    );
  }

  const hex = parsed.data?.audio;
  if (!hex) {
    return NextResponse.json({ error: 'No audio returned' }, { status: 502 });
  }

  const audioBuffer = Buffer.from(hex, 'hex');
  const generationMs = Date.now() - started;

  return new NextResponse(audioBuffer, {
    status: 200,
    headers: {
      'Content-Type': 'audio/mpeg',
      'X-Generation-Ms': String(generationMs),
      'X-Voice-Id': voiceId,
      'X-Emotion': payload.voice_setting.emotion,
      'Cache-Control': 'no-store',
    },
  });
}

export async function GET() {
  if (process.env.NODE_ENV === 'production') {
    return NextResponse.json({ error: 'Not available in production' }, { status: 404 });
  }

  return NextResponse.json({
    voices: VOICE_OPTIONS,
    emotions: EMOTIONS,
    defaults: {
      model: process.env.MINIMAX_TTS_MODEL || 'speech-2.8-hd',
      speed: Number(process.env.MINIMAX_SPEED ?? 1),
      volume: Number(process.env.MINIMAX_VOLUME ?? 1),
      pitch: Number(process.env.MINIMAX_PITCH ?? 0),
      emotion: process.env.MINIMAX_EMOTION || 'neutral',
      phrases: {
        es: 'Hola, soy Aria. Cuéntame qué pasó.',
        en: 'Hi, I was in a car accident yesterday. I need help starting my claim.',
      },
    },
  });
}
