import type { RefObject } from "react";

type TrainingUploadControlsProps = {
  trainFileRef: RefObject<HTMLInputElement | null>;
  onSelectTrainingFile: (file: File | null) => void;
};

export default function TrainingUploadControls({ trainFileRef, onSelectTrainingFile }: TrainingUploadControlsProps) {
  return (
    <input
      ref={trainFileRef}
      type="file"
      accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
      className="hidden"
      onChange={(event) => onSelectTrainingFile(event.target.files?.[0] ?? null)}
    />
  );
}
