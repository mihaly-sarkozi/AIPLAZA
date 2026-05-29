import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "../../../store/authStore";
import type { RoleUser } from "../components/rolesTypes";
import RolesPage from "./RolesPage";

type MutationMock<TPayload> = {
  isPending: boolean;
  mutate: ReturnType<typeof vi.fn<(payload: TPayload, options?: { onSuccess?: (data: RoleUser) => void; onError?: (err: unknown) => void }) => void>>;
};

const useUsersMock = vi.fn();
const useCreateUserMutationMock = vi.fn();
const useUpdateUserMutationMock = vi.fn();
const useDeleteUserMutationMock = vi.fn();
const useResendInviteMutationMock = vi.fn();
const useKbListMock = vi.fn();

vi.mock("../hooks/useUsers", () => ({
  useUsers: (...args: unknown[]) => useUsersMock(...args),
  useCreateUserMutation: (...args: unknown[]) => useCreateUserMutationMock(...args),
  useUpdateUserMutation: (...args: unknown[]) => useUpdateUserMutationMock(...args),
  useDeleteUserMutation: (...args: unknown[]) => useDeleteUserMutationMock(...args),
  useResendInviteMutation: (...args: unknown[]) => useResendInviteMutationMock(...args),
}));

vi.mock("../../knowledge-base/hooks/useKb", () => ({
  useKbList: (...args: unknown[]) => useKbListMock(...args),
}));

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

const owner: RoleUser = {
  id: 1,
  email: "owner@example.test",
  name: "Owner User",
  role: "owner",
  is_active: true,
};

const admin: RoleUser = {
  id: 2,
  email: "admin@example.test",
  name: "Admin User",
  role: "admin",
  is_active: true,
};

const regularUser: RoleUser = {
  id: 3,
  email: "user@example.test",
  name: "Regular User",
  role: "user",
  is_active: true,
};

const inactiveUser: RoleUser = {
  id: 4,
  email: "inactive@example.test",
  name: "Inactive User",
  role: "user",
  is_active: false,
};

function createMutationMock<TPayload>(): MutationMock<TPayload> {
  return {
    isPending: false,
    mutate: vi.fn((payload, options) => {
      options?.onSuccess?.({ ...regularUser, ...payload });
    }),
  };
}

function setupRolesPage(users: RoleUser[] = [owner, admin, regularUser, inactiveUser]) {
  const createMutation = createMutationMock<{ email: string; name?: string; role: string }>();
  const updateMutation = createMutationMock<{ id: number; name: string; email?: string; role?: string; is_active?: boolean }>();
  const deleteMutation = createMutationMock<number>();
  const resendMutation = createMutationMock<number>();

  useAuthStore.setState({
    token: "access",
    user: { id: admin.id, email: admin.email, name: admin.name, role: "admin" },
    loadingUser: false,
  });

  useUsersMock.mockReturnValue({ data: users, isLoading: false, error: null });
  useKbListMock.mockReturnValue({ data: [] });
  useCreateUserMutationMock.mockReturnValue(createMutation);
  useUpdateUserMutationMock.mockReturnValue(updateMutation);
  useDeleteUserMutationMock.mockReturnValue(deleteMutation);
  useResendInviteMutationMock.mockReturnValue(resendMutation);

  const view = render(<RolesPage />);
  return { ...view, createMutation, updateMutation, deleteMutation, resendMutation };
}

async function openCreateModal() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "+ Új felhasználó" }));
  return user;
}

async function openEditModalFor(name: string) {
  const user = userEvent.setup();
  const row = screen.getByText(name).closest(".grid");
  expect(row).not.toBeNull();
  await user.click(within(row as HTMLElement).getByRole("button", { name: "Beállítások" }));
  return user;
}

describe("RolesPage user management", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ token: null, user: null, loadingUser: false });
  });

  it("does not create a user when required fields are empty", async () => {
    const { createMutation } = setupRolesPage();
    const user = await openCreateModal();

    await user.click(screen.getByRole("button", { name: "Létrehozás" }));

    expect(screen.getByText("A név és az email megadása kötelező.")).toBeInTheDocument();
    expect(createMutation.mutate).not.toHaveBeenCalled();
  });

  it("creates a user with trimmed name, email and selected role", async () => {
    const { createMutation } = setupRolesPage();
    const user = await openCreateModal();

    await user.type(screen.getByPlaceholderText("Felhasználó neve"), "  New Admin  ");
    await user.type(screen.getByPlaceholderText("Ide megy a regisztrációs link"), "  new-admin@example.test  ");
    await user.selectOptions(screen.getByRole("combobox"), "admin");
    await user.click(screen.getByRole("button", { name: "Létrehozás" }));

    expect(createMutation.mutate).toHaveBeenCalledWith(
      { email: "new-admin@example.test", name: "New Admin", role: "admin" },
      expect.any(Object)
    );
  });

  it("validates edit fields before saving changes", async () => {
    const { updateMutation } = setupRolesPage();
    const user = await openEditModalFor("Regular User");

    await user.clear(screen.getByDisplayValue("Regular User"));
    await user.click(screen.getByRole("button", { name: "Mentés" }));

    expect(screen.getByText("A név megadása kötelező.")).toBeInTheDocument();
    expect(updateMutation.mutate).not.toHaveBeenCalled();
  });

  it("saves edited name, email and role for another user", async () => {
    const { updateMutation } = setupRolesPage();
    const user = await openEditModalFor("Regular User");

    await user.clear(screen.getByDisplayValue("Regular User"));
    await user.type(screen.getByPlaceholderText("Felhasználó neve"), "Renamed User");
    await user.clear(screen.getByDisplayValue("user@example.test"));
    await user.type(screen.getByPlaceholderText("email@pelda.hu"), "renamed@example.test");
    await user.selectOptions(screen.getByRole("combobox"), "admin");
    await user.click(screen.getByRole("button", { name: "Mentés" }));

    expect(updateMutation.mutate).toHaveBeenCalledWith(
      { id: regularUser.id, name: "Renamed User", email: "renamed@example.test", role: "admin" },
      expect.any(Object)
    );
  });

  it("rejects an invalid email while editing another user", async () => {
    const { updateMutation } = setupRolesPage();
    const user = await openEditModalFor("Regular User");

    await user.clear(screen.getByDisplayValue("user@example.test"));
    await user.type(screen.getByPlaceholderText("email@pelda.hu"), "not-an-email");
    await user.click(screen.getByRole("button", { name: "Mentés" }));

    expect(screen.getByText("Az email cím formátuma nem megfelelő.")).toBeInTheDocument();
    expect(updateMutation.mutate).not.toHaveBeenCalled();
  });

  it("does not allow editing the current admin role", async () => {
    setupRolesPage();

    await openEditModalFor("Admin User");
    const dialog = screen.getByRole("dialog");

    expect(within(dialog).getByText("Adminisztrátor")).toBeInTheDocument();
    expect(within(dialog).queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("saves current admin edits without sending a role change", async () => {
    const { updateMutation } = setupRolesPage();
    const user = await openEditModalFor("Admin User");

    await user.clear(screen.getByDisplayValue("Admin User"));
    await user.type(screen.getByPlaceholderText("Felhasználó neve"), "Admin Renamed");
    await user.clear(screen.getByDisplayValue("admin@example.test"));
    await user.type(screen.getByPlaceholderText("email@pelda.hu"), "admin-new@example.test");
    await user.click(screen.getByRole("button", { name: "Mentés" }));

    expect(updateMutation.mutate).toHaveBeenCalledWith(
      { id: admin.id, name: "Admin Renamed", email: "admin-new@example.test" },
      expect.any(Object)
    );
  });

  it("does not show an active switch for the current user", () => {
    setupRolesPage();

    const row = screen.getByText("Admin User").closest(".grid");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).queryByRole("switch")).not.toBeInTheDocument();
  });

  it("toggles another active user without changing email or role", async () => {
    const { updateMutation } = setupRolesPage();
    const user = userEvent.setup();
    const row = screen.getByText("Regular User").closest(".grid");
    expect(row).not.toBeNull();

    await user.click(within(row as HTMLElement).getByRole("switch"));

    expect(updateMutation.mutate).toHaveBeenCalledWith(
      { id: regularUser.id, name: "Regular User", is_active: false },
      expect.any(Object)
    );
  });
});
