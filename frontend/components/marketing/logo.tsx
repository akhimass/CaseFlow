import { cn } from '@/lib/shadcn/utils';

type IconProps = { className?: string };

/** Flowing wave mark evoking the "flow" in caseflowy — scales via className. */
export function CaseflowIcon({ className }: IconProps) {
  return (
    <svg
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
      className={cn('text-foreground shrink-0', className)}
    >
      <g stroke="currentColor" strokeWidth="4" strokeLinecap="round" fill="none">
        <path d="M14 25 C20 19, 26 19, 32 25 S44 31, 50 25" />
        <path d="M14 32 C20 26, 26 26, 32 32 S44 38, 50 32" />
        <path d="M14 39 C20 33, 26 33, 32 39 S44 45, 50 39" />
      </g>
    </svg>
  );
}

/** Icon only — header sidebar, previews. */
export function LogoMark({ className }: IconProps) {
  return <CaseflowIcon className={cn('size-8 sm:size-9', className)} />;
}

/** Icon + caseflow wordmark for nav and footer. */
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)} aria-label="Caseflowy">
      <CaseflowIcon className="size-9 sm:size-10" />
      <span className="text-[1.25rem] leading-none font-semibold tracking-tight lowercase sm:text-[1.4rem]">
        caseflowy
      </span>
    </span>
  );
}
