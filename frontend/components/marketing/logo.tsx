import { cn } from '@/lib/shadcn/utils';

type IconProps = { className?: string };

/** Folder with camera centered — scales via className (e.g. size-9). */
export function CaseflowIcon({ className }: IconProps) {
  return (
    <svg
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
      className={cn('text-foreground shrink-0', className)}
    >
      {/* Folder */}
      <path
        d="M10 22.5V44.5C10 46.4 11.6 48 13.5 48H50.5C52.4 48 54 46.4 54 44.5V26.5C54 24.6 52.4 23 50.5 23H38.5L34.5 19H13.5C11.6 19 10 20.6 10 22.5Z"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M10 30H18.5C22 30 24.5 32.5 27 34C29.5 35.5 32 38 35.5 38H54"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Camera body */}
      <rect x="22" y="31" width="20" height="13" rx="2.5" stroke="currentColor" strokeWidth="2.5" />
      {/* Lens */}
      <circle cx="32" cy="37.5" r="4.25" stroke="currentColor" strokeWidth="2.5" />
      <circle cx="32" cy="37.5" r="1.75" fill="currentColor" />
      {/* Viewfinder */}
      <path
        d="M27 31V28.5C27 27.7 27.7 27 28.5 27H35.5C36.3 27 37 27.7 37 28.5V31"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Flash dot */}
      <circle cx="39" cy="33.5" r="1.25" fill="currentColor" />
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
