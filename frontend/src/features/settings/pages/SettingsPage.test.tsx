// frontend/src/features/settings/pages/SettingsPage.test.tsx
// Feladat: SettingsPage belépési pont jogosultsági viselkedésének tesztelése.
// Sárközi Mihály - 2026.05.29

import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SettingsPage from "./SettingsPage";
import { useAuthStore } from "../../../store/authStore";

vi.mock("../shell/SettingsShell", () => ({
  default: () => <div>settings-shell</div>,
}));

describe("SettingsPage access", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null, user: null, loadingUser: false });
  });

  it("shows access denied for non-owner/admin", () => {
    useAuthStore.setState({ token: "x", user: { id: 1, email: "u@example.test", role: "user" }, loadingUser: false });
    render(<SettingsPage />);
    expect(screen.getByText(/owner/i)).toBeInTheDocument();
  });

  it("renders settings shell for owner", () => {
    useAuthStore.setState({ token: "x", user: { id: 1, email: "o@example.test", role: "owner" }, loadingUser: false });
    render(<SettingsPage />);
    expect(screen.getByText("settings-shell")).toBeInTheDocument();
  });

  it("renders settings shell for admin", () => {
    useAuthStore.setState({ token: "x", user: { id: 1, email: "a@example.test", role: "admin" }, loadingUser: false });
    render(<SettingsPage />);
    expect(screen.getByText("settings-shell")).toBeInTheDocument();
  });
});
