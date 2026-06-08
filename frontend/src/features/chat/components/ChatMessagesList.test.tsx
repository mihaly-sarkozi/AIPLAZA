import { createRef } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ChatMessagesList from "./ChatMessagesList";

vi.mock("./ChatMessage", () => ({
  default: ({ role, text }: { role: string; text: string }) => <div data-testid={`message-${role}`}>{text}</div>,
}));

const t = (key: string) => ({ "chat.emptyState": "Nincs még üzenet" })[key] ?? key;

function baseProps(overrides: Partial<React.ComponentProps<typeof ChatMessagesList>> = {}) {
  return {
    contextNotice: null,
    messages: [],
    loading: false,
    fileCountingProgress: null,
    activeTrainingTitle: null,
    displayedTrainingProgress: 0,
    messagesEndRef: createRef<HTMLDivElement>(),
    t,
    ...overrides,
  };
}

describe("ChatMessagesList", () => {
  it("üres állapotot jelenít meg üzenetek nélkül", () => {
    render(<ChatMessagesList {...baseProps()} />);

    expect(screen.getByText("Nincs még üzenet")).toBeInTheDocument();
  });

  it("kirendereli a context notice-t és az üzeneteket", () => {
    render(
      <ChatMessagesList
        {...baseProps({
          contextNotice: "Kontextus értesítés",
          messages: [
            { role: "user", text: "Szia" },
            { role: "assistant", text: "Válasz" },
          ],
        })}
      />
    );

    expect(screen.getByText("Kontextus értesítés")).toBeInTheDocument();
    expect(screen.getByText("Szia")).toBeInTheDocument();
    expect(screen.getByText("Válasz")).toBeInTheDocument();
  });

});
