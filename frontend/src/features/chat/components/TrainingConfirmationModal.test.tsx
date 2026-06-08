import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import TrainingConfirmationModal from "./TrainingConfirmationModal";

const t = (key: string) =>
  (
    {
      "chat.fileCharacterCount": "{{count}} karakter.",
      "chat.trainingStartQuestion": "Indulhat a tanítás?",
      "chat.trainingStartCancel": "Mégse",
      "chat.trainingStartConfirm": "Indulhat",
    } as Record<string, string>
  )[key] ?? key;

describe("TrainingConfirmationModal", () => {
  it("megjeleníti a karakterszámot és a megerősítő gombokat", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();

    render(
      <TrainingConfirmationModal
        open
        filename="training.txt"
        characterCount={89002}
        locale="hu-HU"
        onCancel={onCancel}
        onConfirm={onConfirm}
        t={t}
      />
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("training.txt")).toBeInTheDocument();
    expect(screen.getByText("89 002 karakter. Indulhat a tanítás?")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Indulhat" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByRole("button", { name: "Mégse" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("zárt állapotban nem renderel", () => {
    render(
      <TrainingConfirmationModal
        open={false}
        filename="training.txt"
        characterCount={100}
        locale="hu-HU"
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
        t={t}
      />
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
