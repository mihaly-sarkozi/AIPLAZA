import { useTranslation } from "../../../../i18n";
import { translateProcessingMonitorKey } from "../../utils/processingMonitorUtils";
import type { ProcessingFlowSummary } from "../../utils/processingMonitorUtils";

type ProcessingMonitorLiveBannerProps = {
  isLive: boolean;
  activeFlowCount?: number;
  activeFlow?: Pick<
    ProcessingFlowSummary,
    "activeModule" | "activeStage" | "activeStep" | "latestMessage"
  > | null;
};

export default function ProcessingMonitorLiveBanner({
  isLive,
  activeFlowCount = 0,
  activeFlow = null,
}: ProcessingMonitorLiveBannerProps) {
  const { t } = useTranslation();

  if (!isLive) return null;

  const moduleLabel = activeFlow?.activeModule
    ? translateProcessingMonitorKey(t, activeFlow.activeModule, "module")
    : null;
  const stepLabel = activeFlow?.activeStep
    ? translateProcessingMonitorKey(t, activeFlow.activeStep, "stepOrStage")
    : null;
  const stageLabel = activeFlow?.activeStage
    ? translateProcessingMonitorKey(t, activeFlow.activeStage, "stage")
    : null;
  const progressParts = [moduleLabel, stageLabel ?? stepLabel].filter(Boolean);
  const progressText = progressParts.length
    ? t("kb.processingMonitor.activeProgress")
        .replace("{{module}}", progressParts[0] ?? "")
        .replace("{{step}}", progressParts[1] ?? progressParts[0] ?? "")
    : null;

  return (
    <div
      className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-950"
      role="status"
      aria-live="polite"
    >
      <span className="relative flex h-2.5 w-2.5 shrink-0" aria-hidden="true">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-75" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-sky-500" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-medium">{t("kb.processingMonitor.liveUpdating")}</p>
        {progressText ? <p className="mt-0.5 text-sky-900">{progressText}</p> : null}
        {activeFlow?.latestMessage && !progressText ? (
          <p className="mt-0.5 text-sky-900">{activeFlow.latestMessage}</p>
        ) : null}
        {activeFlowCount > 1 ? (
          <p className="mt-0.5 text-xs text-sky-800">
            {t("kb.processingMonitor.activeFlowCount").replace("{{count}}", String(activeFlowCount))}
          </p>
        ) : null}
      </div>
    </div>
  );
}
