import type { StepSummaryDisplay } from "../../utils/stepSummaryDisplay";
import ProcessingKeyValueTable from "./ProcessingKeyValueTable";

type ProcessingStepSummaryPanelProps = {
  title: string;
  display: StepSummaryDisplay;
  emptyLabel: string;
};

export default function ProcessingStepSummaryPanel({
  title,
  display,
  emptyLabel,
}: ProcessingStepSummaryPanelProps) {
  return (
    <ProcessingKeyValueTable title={title} rows={display.rows} emptyLabel={emptyLabel} />
  );
}
