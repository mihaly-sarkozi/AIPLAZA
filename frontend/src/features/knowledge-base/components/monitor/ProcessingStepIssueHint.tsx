import type { ProcessingIssueSummary } from "../../../../api/services/kb/kbProcessingApi";
import { translateProcessingMonitorKey } from "../../utils/processingMonitorUtils";

type ProcessingStepIssueHintProps = {
  issues: ProcessingIssueSummary[];
  t: (key: string) => string;
};

function issueDetailLine(
  issue: ProcessingIssueSummary,
  t: (key: string) => string,
): string {
  const label = translateProcessingMonitorKey(t, issue.issue_code, "issue");
  const message = (issue.issue_message ?? "").trim();
  if (message && message !== label) {
    return `${label}: ${message}`;
  }
  return label || message;
}

export default function ProcessingStepIssueHint({ issues, t }: ProcessingStepIssueHintProps) {
  const open = issues.filter((issue) => issue.status === "OPEN");
  if (!open.length) return null;

  const hasError = open.some((issue) => ["ERROR", "CRITICAL"].includes(issue.severity));
  const lines = open.map((issue) => issueDetailLine(issue, t));
  const ariaLabel = t("kb.processingMonitor.stepIssueHintAria");

  return (
    <div className="group relative inline-flex shrink-0" aria-label={ariaLabel}>
      <div
        className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-2 w-max max-w-[18rem] -translate-x-1/2 whitespace-normal rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-left text-xs leading-snug text-amber-950 opacity-0 shadow-md transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100"
        role="tooltip"
      >
        <ul className="space-y-1">
          {lines.map((line, index) => (
            <li key={`${line}-${index}`}>{line}</li>
          ))}
        </ul>
      </div>
      <button
        type="button"
        className="inline-flex h-6 w-6 items-center justify-center rounded-md text-amber-600 hover:bg-amber-100/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
        tabIndex={0}
        aria-label={ariaLabel}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
        }}
      >
        <svg
          viewBox="0 0 24 24"
          className="h-4 w-4"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
        {hasError ? (
          <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-red-500" aria-hidden="true" />
        ) : null}
      </button>
    </div>
  );
}
