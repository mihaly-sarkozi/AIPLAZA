import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import ProtectedRoute from "./ProtectedRoute";
import { useAuthStore, type User } from "../state/authStore";

function renderProtected(
  auth: { token: string | null; user: User | null; loadingUser?: boolean },
  props: Partial<Parameters<typeof ProtectedRoute>[0]> = {},
  initialPath = "/admin/users"
) {
  useAuthStore.setState({
    token: auth.token,
    user: auth.user,
    loadingUser: auth.loadingUser ?? false,
  });
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route
          path={initialPath}
          element={
            <ProtectedRoute {...props}>
              <div>Protected content</div>
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null, user: null, loadingUser: false });
  });

  it("redirects to login without token", () => {
    renderProtected({ token: null, user: null });
    expect(screen.getByText("Login page")).toBeInTheDocument();
  });

  it("shows loading fallback while user is loading", () => {
    renderProtected(
      { token: "access", user: null, loadingUser: true },
      { loadingFallback: <div>Loading user</div> }
    );
    expect(screen.getByText("Loading user")).toBeInTheDocument();
  });

  it("shows access denied when required permission is missing", () => {
    renderProtected(
      { token: "access", user: { id: 1, email: "u@example.test", role: "user" } },
      { requiredPermission: "users.write" }
    );
    expect(screen.getByText("Nincs jogosultságod az oldal megtekintéséhez.")).toBeInTheDocument();
  });

  it("renders children when required permission is present", () => {
    renderProtected(
      { token: "access", user: { id: 1, email: "a@example.test", role: "admin" } },
      { requiredPermission: "users.write" }
    );
    expect(screen.getByText("Protected content")).toBeInTheDocument();
  });

  it("supports owner wildcard permissions", () => {
    renderProtected(
      { token: "access", user: { id: 1, email: "o@example.test", role: "owner" } },
      { requiredPermission: "chat.channel.manage" }
    );
    expect(screen.getByText("Protected content")).toBeInTheDocument();
  });

  it("keeps chat channel management owner-only at route level", () => {
    renderProtected(
      { token: "access", user: { id: 1, email: "admin@example.test", role: "admin" } },
      { requiredPermission: "chat.channel.manage" }
    );
    expect(screen.getByText("Nincs jogosultságod az oldal megtekintéséhez.")).toBeInTheDocument();
  });
});
