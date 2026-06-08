type TextTrainingPendingIndicatorProps = {
  detail: string;
  ariaLabel: string;
};

export default function TextTrainingPendingIndicator({ detail, ariaLabel }: TextTrainingPendingIndicatorProps) {
  return (
    <div className="group relative shrink-0 self-center -translate-y-px" aria-label={ariaLabel} title={detail}>
      <div
        className="pointer-events-none absolute top-full right-0 z-30 mt-1.5 max-w-[14rem] -translate-x-3 whitespace-normal rounded-md border border-[var(--color-border)] bg-[var(--color-card)] px-2 py-1 text-right text-xs leading-snug text-[var(--color-muted)] opacity-0 shadow-sm transition-opacity duration-150 group-hover:opacity-100"
        role="tooltip"
      >
        {detail}
      </div>
      <div className="flex h-5 w-5 items-center justify-center" aria-hidden="true">
        <svg
          className="h-4 w-4 animate-spin text-[var(--color-primary)]"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8" />
          <path d="M21 3v5h-5" />
        </svg>
      </div>
    </div>
  );
}
