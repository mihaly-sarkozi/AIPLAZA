import type { TextTrainingOutcome } from "../../utils/textTrainingMessage";

type TextTrainingOutcomeIndicatorProps = {
  outcome: TextTrainingOutcome;
  detail: string;
  successLabel: string;
  errorLabel: string;
  cancelledLabel: string;
};

export default function TextTrainingOutcomeIndicator({
  outcome,
  detail,
  successLabel,
  errorLabel,
  cancelledLabel,
}: TextTrainingOutcomeIndicatorProps) {
  const isSuccess = outcome === "success";
  const isCancelled = outcome === "cancelled";
  const ariaLabel = isSuccess ? successLabel : isCancelled ? cancelledLabel : errorLabel;

  return (
    <div
      className="group relative shrink-0 self-center -translate-y-px"
      aria-label={ariaLabel}
      title={detail}
    >
      <div
        className={`pointer-events-none absolute top-full right-0 z-30 mt-1.5 max-w-[14rem] -translate-x-3 whitespace-normal rounded-md border px-2 py-1 text-right text-xs leading-snug opacity-0 shadow-sm transition-opacity duration-150 group-hover:opacity-100 ${
          isSuccess
            ? "border-[var(--color-success-border)] bg-[var(--color-success-bg)] text-[var(--color-success-text)]"
            : "border-red-300/50 bg-[var(--color-card)] text-red-500"
        }`}
        role="tooltip"
      >
        {detail}
      </div>
      <div className="flex h-5 w-5 items-center justify-center" aria-hidden="true">
        {isSuccess ? (
          <svg
            className="h-4 w-4 text-[var(--color-success-text)]"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M20 6 9 17l-5-5" />
          </svg>
        ) : isCancelled ? (
          <svg
            className="h-4 w-4 text-red-500"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M18 6 6 18" />
            <path d="m6 6 12 12" />
          </svg>
        ) : (
          <svg
            className="h-4 w-4 text-red-500"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="9" />
            <path d="M12 8v4" />
            <path d="M12 16h.01" />
          </svg>
        )}
      </div>
    </div>
  );
}
