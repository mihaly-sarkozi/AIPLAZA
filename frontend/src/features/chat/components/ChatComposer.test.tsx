import { createRef } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ChatComposer from "./ChatComposer";

const t = (key: string) =>
  ({
    "chat.newChat": "Új chat",
    "chat.selectTrainingFile": "Tanító fájl kiválasztása",
    "chat.startTraining": "Tanítás indítása",
    "chat.sendQuestion": "Kérdés küldése",
    "chat.trainPlaceholder": "Tanító szöveg",
    "chat.queryPlaceholder": "Kérdés",
    "chat.chatModeLabel": "Chat mód",
    "chat.modeQuery": "Kérdés",
    "chat.modeTrain": "Tanítás",
    "chat.kbSelectorLabel": "Tudástár kiválasztása",
    "chat.allKbs": "Összes tudástár",
  })[key] ?? key;

function renderComposer(overrides: Partial<React.ComponentProps<typeof ChatComposer>> = {}) {
  const props: React.ComponentProps<typeof ChatComposer> = {
    chatMode: "query",
    setChatMode: vi.fn(),
    dragOverTrainFile: false,
    setDragOverTrainFile: vi.fn(),
    inputDraft: "",
    setInputDraft: vi.fn(),
    loading: false,
    messagesLength: 1,
    contextNotice: null,
    trainingOperationRunning: false,
    pendingTrainingConfirmation: false,
    selectedTopKbUuid: "kb-1",
    selectedTopKbLabel: "Smoke KB",
    selectableChatKbList: [{ uuid: "kb-1", name: "Smoke KB" }],
    trainableKbList: [{ uuid: "kb-1", name: "Smoke KB" }],
    composerUsage: { percent: 50, label: "50%", title: "Usage" },
    inputRef: createRef<HTMLInputElement>(),
    trainFileRef: createRef<HTMLInputElement>(),
    onSelectTrainingFile: vi.fn(),
    clearHistory: vi.fn(),
    exportChatProcess: vi.fn(),
    send: vi.fn(),
    onSubmitTextTraining: vi.fn(),
    setSelectedTrainKbUuid: vi.fn(),
    setSelectedChatKbUuid: vi.fn(),
    t,
    ...overrides,
  };
  render(<ChatComposer {...props} />);
  return props;
}

describe("ChatComposer", () => {
  it("Enterrel elküldi a kérdést query módban", () => {
    const props = renderComposer({ inputDraft: "hello" });

    fireEvent.keyDown(screen.getByPlaceholderText("Kérdés"), { key: "Enter" });

    expect(props.send).toHaveBeenCalledTimes(1);
    expect(props.onSubmitTextTraining).not.toHaveBeenCalled();
  });

  it("Enterrel tanítást indít train módban", () => {
    const props = renderComposer({ chatMode: "train", inputDraft: "training text" });

    fireEvent.keyDown(screen.getByPlaceholderText("Tanító szöveg"), { key: "Enter" });

    expect(props.onSubmitTextTraining).toHaveBeenCalledTimes(1);
    expect(props.send).not.toHaveBeenCalled();
  });

  it("fájl drop esetén átadja a kiválasztott fájlt", async () => {
    const user = userEvent.setup();
    const props = renderComposer({ chatMode: "train" });
    const file = new File(["content"], "training.txt", { type: "text/plain" });
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(fileInput, file);

    expect(props.onSelectTrainingFile).toHaveBeenCalledWith(file);
  });

  it("nem mutatja a tanítás módot, ha nincs tanítható tudástár", () => {
    renderComposer({ trainableKbList: [] });

    expect(screen.queryByRole("option", { name: "Tanítás" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Kérdés" })).toBeInTheDocument();
  });
});
