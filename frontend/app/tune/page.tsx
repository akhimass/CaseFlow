'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

type VoiceCatalog = { es: string[]; en: string[] };
type Lang = 'es' | 'en';

const DEFAULT_PHRASES: Record<Lang, string> = {
  es: 'Hola, soy Aria. Cuéntame qué pasó.',
  en: 'Hi, I was in a car accident yesterday. I need help starting my claim.',
};

export default function TunePage() {
  const [catalog, setCatalog] = useState<VoiceCatalog>({ es: [], en: [] });
  const [emotions, setEmotions] = useState<string[]>(['neutral', 'calm']);
  const [language, setLanguage] = useState<Lang>('es');
  const [voiceId, setVoiceId] = useState('');
  const [speed, setSpeed] = useState(1);
  const [volume, setVolume] = useState(1);
  const [pitch, setPitch] = useState(0);
  const [emotion, setEmotion] = useState('neutral');
  const [text, setText] = useState(DEFAULT_PHRASES.es);
  const [status, setStatus] = useState<string>('Loading catalog…');
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  const voices = useMemo(() => catalog[language] ?? [], [catalog, language]);

  useEffect(() => {
    if (process.env.NODE_ENV === 'production') {
      setStatus('Tune panel is disabled in production builds.');
      return;
    }

    fetch('/api/dev/tts-preview')
      .then((r) => r.json())
      .then((data) => {
        setCatalog(data.voices ?? { es: [], en: [] });
        setEmotions(data.emotions ?? ['neutral', 'calm']);
        if (data.defaults?.emotion) setEmotion(data.defaults.emotion);
        if (data.defaults?.speed) setSpeed(data.defaults.speed);
        if (data.defaults?.volume) setVolume(data.defaults.volume);
        if (data.defaults?.pitch) setPitch(data.defaults.pitch);
        setStatus('Ready');
      })
      .catch(() => setStatus('Failed to load voice catalog'));
  }, []);

  useEffect(() => {
    setText(DEFAULT_PHRASES[language]);
    const first = voices[0];
    if (first) setVoiceId(first);
  }, [language, voices]);

  const cleanupAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
  }, []);

  const playPreview = async () => {
    cleanupAudio();
    setPlaying(true);
    setStatus('Generating…');

    try {
      const res = await fetch('/api/dev/tts-preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text,
          language,
          voiceId,
          speed,
          volume,
          pitch,
          emotion,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${res.status}`);
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      objectUrlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      const genMs = res.headers.get('X-Generation-Ms');
      setStatus(genMs ? `Played (${genMs} ms generation)` : 'Played');
      await audio.play();
      audio.onended = () => setPlaying(false);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : 'Playback failed');
      setPlaying(false);
    }
  };

  if (process.env.NODE_ENV === 'production') {
    return (
      <main className="mx-auto max-w-3xl p-8">
        <h1 className="text-2xl font-semibold">Caseflowy Voice Tuning</h1>
        <p className="text-muted-foreground mt-2">Unavailable in production.</p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 p-8">
      <header>
        <p className="text-muted-foreground text-sm tracking-wide uppercase">Dev only</p>
        <h1 className="text-3xl font-semibold">MiniMax Voice Tuning</h1>
        <p className="text-muted-foreground mt-2">
          Tune Spanish and English intake voices for Aria without redeploying the agent.
        </p>
      </header>

      <section className="grid gap-4 rounded-xl border p-5">
        <label className="grid gap-1 text-sm">
          Language
          <select
            className="border-input bg-background rounded-md border px-3 py-2"
            value={language}
            onChange={(e) => setLanguage(e.target.value as Lang)}
          >
            <option value="es">Spanish</option>
            <option value="en">English</option>
          </select>
        </label>

        <label className="grid gap-1 text-sm">
          Voice ID ({language.toUpperCase()})
          <select
            className="border-input bg-background rounded-md border px-3 py-2"
            value={voiceId}
            onChange={(e) => setVoiceId(e.target.value)}
          >
            {voices.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>

        <label className="grid gap-1 text-sm">
          Emotion
          <select
            className="border-input bg-background rounded-md border px-3 py-2"
            value={emotion}
            onChange={(e) => setEmotion(e.target.value)}
          >
            {emotions.map((e) => (
              <option key={e} value={e}>
                {e}
              </option>
            ))}
          </select>
        </label>

        <label className="grid gap-1 text-sm">
          Speed ({speed.toFixed(2)})
          <input
            type="range"
            min={0.5}
            max={1.5}
            step={0.01}
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
          />
        </label>

        <label className="grid gap-1 text-sm">
          Volume ({volume.toFixed(2)})
          <input
            type="range"
            min={0.5}
            max={1.5}
            step={0.01}
            value={volume}
            onChange={(e) => setVolume(Number(e.target.value))}
          />
        </label>

        <label className="grid gap-1 text-sm">
          Pitch ({pitch})
          <input
            type="range"
            min={-12}
            max={12}
            step={1}
            value={pitch}
            onChange={(e) => setPitch(Number(e.target.value))}
          />
        </label>

        <label className="grid gap-1 text-sm">
          Test phrase
          <textarea
            className="border-input bg-background min-h-24 rounded-md border px-3 py-2"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </label>

        <button
          type="button"
          className="bg-primary text-primary-foreground rounded-md px-4 py-2 font-medium disabled:opacity-50"
          disabled={playing || !voiceId}
          onClick={playPreview}
        >
          {playing ? 'Playing…' : 'Play'}
        </button>

        <p className="text-muted-foreground text-sm">{status}</p>
      </section>
    </main>
  );
}
