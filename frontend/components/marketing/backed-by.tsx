import { YCombinatorWordmark } from '@/components/marketing/y-combinator-wordmark';
import { cn } from '@/lib/shadcn/utils';

const LABEL_CLASS =
  'text-[10px] font-semibold uppercase leading-snug tracking-[0.18em] text-muted-foreground sm:text-xs sm:tracking-[0.22em]';

/** Fixed-size cells so logos align on a shared baseline (FirstCall-style). */
const LOGO_CELL = 'flex h-8 w-[5.5rem] items-center justify-center sm:h-9 sm:w-24';

export const SPONSORS = [
  { name: 'LiveKit', src: '/sponsors/livekit.svg' },
  { name: 'TrueFoundry', src: '/sponsors/truefoundry.svg' },
  { name: 'AWS', src: '/sponsors/aws.svg' },
  { name: 'MiniMax', src: '/sponsors/minimax.svg' },
  { name: 'Unsiloed AI', src: '/sponsors/unsiloed.svg' },
  { name: 'Qwen', src: '/sponsors/qwen.svg' },
  { name: 'Moss', src: '/sponsors/moss.svg' },
] as const;

export function BackedBy({
  className,
  align = 'center',
}: {
  className?: string;
  align?: 'center' | 'start';
}) {
  const isStart = align === 'start';

  return (
    <div
      className={cn(
        'flex flex-col gap-5',
        isStart
          ? 'items-center lg:items-start'
          : 'items-center sm:flex-row sm:justify-center sm:gap-8',
        className
      )}
    >
      <p
        className={cn(
          'flex max-w-none shrink-0 flex-wrap items-center gap-x-1.5 gap-y-1.5',
          isStart
            ? 'justify-center text-center lg:justify-start lg:text-left'
            : 'justify-center text-center sm:justify-start sm:text-left'
        )}
      >
        <span className={LABEL_CLASS}>Built at</span>
        <YCombinatorWordmark />
        <span className={cn(LABEL_CLASS, 'pl-[1ch]')}>Conversational AI Hackathon with</span>
      </p>
      <ul
        className={cn(
          'flex flex-wrap items-center gap-x-6 gap-y-4 sm:gap-x-8',
          isStart ? 'justify-center lg:justify-start' : 'justify-center sm:gap-x-10'
        )}
      >
        {SPONSORS.map(({ name, src }) => (
          <li key={name} className={LOGO_CELL}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={src}
              alt={name}
              className="max-h-full max-w-full object-contain opacity-55 grayscale transition-opacity hover:opacity-80 dark:opacity-80 dark:invert"
            />
          </li>
        ))}
      </ul>
    </div>
  );
}
