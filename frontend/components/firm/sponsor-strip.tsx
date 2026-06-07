import Image from 'next/image';
import { SPONSORS } from '@/components/marketing/backed-by';

export function SponsorStrip({ compact = false }: { compact?: boolean }) {
  const shown = compact ? SPONSORS.slice(0, 5) : SPONSORS;

  return (
    <div className="flex flex-wrap items-center gap-3">
      {shown.map((sponsor) => (
        <div
          key={sponsor.name}
          className="border-border bg-background/80 flex h-7 w-20 items-center justify-center rounded border px-1"
          title={sponsor.name}
        >
          <Image
            src={sponsor.src}
            alt={sponsor.name}
            width={72}
            height={20}
            className="h-4 w-auto object-contain opacity-80"
          />
        </div>
      ))}
    </div>
  );
}
