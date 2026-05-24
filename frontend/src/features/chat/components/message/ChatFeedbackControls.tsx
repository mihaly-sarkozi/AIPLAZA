type ChatFeedbackControlsProps = {
  feedbackValue: boolean | null;
  feedbackLoading: boolean;
  onSendFeedback: (helpful: boolean) => void;
  t: (key: string) => string;
};

export default function ChatFeedbackControls({
  feedbackValue,
  feedbackLoading,
  onSendFeedback,
  t,
}: ChatFeedbackControlsProps) {
  return (
    <div className="inline-flex items-center gap-1">
      <button
        type="button"
        onClick={() => onSendFeedback(true)}
        disabled={feedbackLoading}
        className={`inline-flex h-6 w-6 items-center justify-center rounded-full border transition hover:text-[var(--color-foreground)] disabled:opacity-60 ${
          feedbackValue === true
            ? "border-[var(--color-success-border)] text-[var(--color-success-text)]"
            : "border-[var(--color-border)] text-[var(--color-muted)]"
        }`}
        aria-label={t("chat.feedbackLike")}
        title={t("chat.feedbackLike")}
      >
        <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M7 10v10M7 10l4.5-6.5c.8-1.1 2.5-.6 2.5.8V9h4.2c1.2 0 2.1 1.1 1.9 2.2l-1.2 6.5A2.8 2.8 0 0 1 16.1 20H7"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      <button
        type="button"
        onClick={() => onSendFeedback(false)}
        disabled={feedbackLoading}
        className={`inline-flex h-6 w-6 items-center justify-center rounded-full border transition hover:text-[var(--color-foreground)] disabled:opacity-60 ${
          feedbackValue === false
            ? "border-[var(--color-danger-border)] text-[var(--color-danger-text)]"
            : "border-[var(--color-border)] text-[var(--color-muted)]"
        }`}
        aria-label={t("chat.feedbackUnlike")}
        title={t("chat.feedbackUnlike")}
      >
        <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M17 14V4M17 14l-4.5 6.5c-.8 1.1-2.5.6-2.5-.8V15H5.8c-1.2 0-2.1-1.1-1.9-2.2l1.2-6.5A2.8 2.8 0 0 1 7.9 4H17"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
    </div>
  );
}
