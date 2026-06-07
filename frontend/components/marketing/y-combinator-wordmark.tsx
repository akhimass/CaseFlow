import { cn } from '@/lib/shadcn/utils';

const YC_ORANGE = '#FF6600';

export function YCombinatorWordmark({ className }: { className?: string }) {
  return (
    <span
      className={cn('inline-flex shrink-0 items-center', className)}
      role="img"
      aria-label="Y Combinator"
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="size-[18px] shrink-0 sm:size-5"
        aria-hidden
      >
        <rect width="24" height="24" fill={YC_ORANGE} />
        <text
          x="12"
          y="17"
          fill="#fff"
          fontFamily="Helvetica, Arial, ui-sans-serif, sans-serif"
          fontSize="14"
          fontWeight="700"
          textAnchor="middle"
        >
          Y
        </text>
      </svg>
      <span
        className="ml-1 text-[15px] leading-none font-semibold tracking-tight text-[#FF6600] sm:text-base"
        style={{ fontFamily: 'Helvetica, Arial, ui-sans-serif, sans-serif' }}
      >
        Combinator
      </span>
    </span>
  );
}
