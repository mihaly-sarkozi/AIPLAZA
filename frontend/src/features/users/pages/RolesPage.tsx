import { useMemo, useState } from "react";
import { toast } from "sonner";
import { useTranslation } from "../../../i18n";
import { useLocaleStore } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import {
  useUsers,
  useCreateUserMutation,
  useUpdateUserMutation,
  useDeleteUserMutation,
  useResendInviteMutation,
  type UserListItem,
} from "../hooks/useUsers";
import { useKbList } from "../../knowledge-base/hooks/useKb";
import UserKbAccessModal from "../components/UserKbAccessModal";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";

type User = UserListItem & { pending_registration?: boolean };

export default function RolesPage() {
  const { t } = useTranslation();
  const { user: currentUser } = useAuthStore();
  const canManage = currentUser?.role === "admin" || currentUser?.role === "owner";
  const { data: usersData, isLoading: loading, error: usersError } = useUsers({ enabled: canManage });
  const users = (usersData ?? []) as User[];
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createFormError, setCreateFormError] = useState<string | null>(null);
  const [editFormError, setEditFormError] = useState<string | null>(null);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [deleteConfirmUser, setDeleteConfirmUser] = useState<User | null>(null);
  const [resendConfirmUser, setResendConfirmUser] = useState<User | null>(null);
  const [userForKbModal, setUserForKbModal] = useState<User | null>(null);

  const { data: kbListData } = useKbList({ enabled: canManage });
  const kbList = useMemo(() => (kbListData ?? []).filter((kb) => kb.can_train), [kbListData]);

  const createUserMutation = useCreateUserMutation();
  const updateUserMutation = useUpdateUserMutation();
  const deleteUserMutation = useDeleteUserMutation();
  const resendInviteMutation = useResendInviteMutation();
  const actionLoading =
    createUserMutation.isPending ||
    updateUserMutation.isPending ||
    deleteUserMutation.isPending ||
    resendInviteMutation.isPending;

  const error = usersError ? (getApiErrorMessage(usersError) ?? t("roles.errorLoad")) : null;

  const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  // Form state
  const [formData, setFormData] = useState({
    email: "",
    name: "",
    role: "user" as "user" | "admin",
    is_active: true,
  });
  const isOwner = (u: User | null) => u?.role === "owner";

  /** Aktívak névsorban előre, inaktívak névsorban hátra */
  const sortedUsers = useMemo(() => {
    const nameKey = (u: User) => (u.name || u.email || "").trim().toLowerCase();
    return [...users].sort((a, b) => {
      if (a.is_active !== b.is_active) return a.is_active ? -1 : 1;
      return nameKey(a).localeCompare(nameKey(b));
    });
  }, [users]);

  const handleCreate = () => {
    const nameTrim = formData.name?.trim() ?? "";
    const emailTrim = formData.email?.trim() ?? "";
    setCreateFormError(null);
    if (!nameTrim || !emailTrim) {
      setCreateFormError(t("roles.createErrorFieldsRequired"));
      return;
    }
    if (!EMAIL_REGEX.test(emailTrim)) {
      setCreateFormError(t("roles.createErrorEmailInvalid"));
      return;
    }
    createUserMutation.mutate(
      { email: emailTrim, name: nameTrim, role: formData.role },
      {
        onSuccess: () => {
          toast.success(t("profile.saved"));
          setShowCreateModal(false);
          resetForm();
          setCreateFormError(null);
        },
        onError: (err: unknown) => {
          const axErr = err as { response?: { status?: number; data?: { detail?: { code?: string } } } };
          const detail = axErr.response?.data?.detail;
          const code = typeof detail === "object" && detail?.code;
          if (axErr.response?.status === 400 && code === "email_already_exists") {
            setCreateFormError(t("roles.createErrorEmailExists"));
          } else {
            toast.error(getApiErrorMessage(err) ?? t("roles.errorCreate"));
          }
        },
      }
    );
  };

  const handleUpdate = () => {
    if (!editingUser) return;

    const nameTrim = formData.name?.trim() ?? "";
    const emailTrim = formData.email?.trim() ?? "";
    const canEditEmail = editingUser.role !== "owner" && editingUser.id !== currentUser?.id;

    setEditFormError(null);
    if (!nameTrim) {
      setEditFormError(t("roles.editErrorNameRequired"));
      return;
    }
    if (canEditEmail) {
      if (!emailTrim) {
        setEditFormError(t("roles.editErrorEmailRequired"));
        return;
      }
      if (!EMAIL_REGEX.test(emailTrim)) {
        setEditFormError(t("roles.createErrorEmailInvalid"));
        return;
      }
    }

    const payload: { id: number; name: string; is_active?: boolean; email?: string; role?: string } = {
      id: editingUser.id,
      name: nameTrim,
    };
    if (editingUser.role !== "owner") {
      if (!editingUser.pending_registration) payload.is_active = formData.is_active;
      if (canEditEmail) payload.email = emailTrim;
      if (editingUser.id !== currentUser?.id) payload.role = formData.role;
    }
    updateUserMutation.mutate(payload, {
      onSuccess: () => {
        toast.success(t("profile.saved"));
        setEditingUser(null);
        resetForm();
        setEditFormError(null);
      },
      onError: (err: unknown) => {
        const axErr = err as { response?: { status?: number; data?: { detail?: { code?: string } } } };
        const detail = axErr.response?.data?.detail;
        const code = typeof detail === "object" && detail?.code;
        if (axErr.response?.status === 400 && code === "email_already_exists") {
          setEditFormError(t("roles.createErrorEmailExists"));
        } else {
          toast.error(getApiErrorMessage(err) ?? t("roles.errorUpdate"));
        }
      },
    });
  };

  const handleDelete = (userId: number): void => {
    deleteUserMutation.mutate(userId, {
      onSuccess: () => {
        toast.success(t("common.delete") + " – OK");
        setDeleteConfirmUser(null);
      },
      onError: (err: unknown) => toast.error(getApiErrorMessage(err) ?? t("roles.errorDelete")),
    });
  };

  const handleResendInvite = (userId: number) => {
    resendInviteMutation.mutate(userId, {
      onSuccess: () => {
        toast.success(t("roles.resendSuccess"));
        setResendConfirmUser(null);
      },
      onError: (err: unknown) => toast.error(getApiErrorMessage(err) ?? t("roles.resendError")),
    });
  };

  const resetForm = () => {
    setFormData({
      email: "",
      name: "",
      role: "user",
      is_active: true,
    });
    setCreateFormError(null);
  };

  const openEditModal = (user: User) => {
    setEditingUser(user);
    setEditFormError(null);
    setFormData({
      email: user.email,
      name: user.name ?? "",
      role: (user.role === "owner" ? "admin" : user.role) as "user" | "admin",
      is_active: user.is_active,
    });
  };

  const localeMap = { hu: "hu-HU", en: "en-GB", es: "es-ES" } as const;
  const dateLocale = localeMap[useLocaleStore((s) => s.locale)] ?? "hu-HU";
  if (!canManage) {
    return (
      <div className="p-6 min-h-full bg-[var(--color-background)]">
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] p-4 rounded">
          {t("roles.noPermission")}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 min-h-full bg-[var(--color-background)]">
      <div className="flex flex-nowrap items-center gap-3 mb-6 min-w-0 w-full">
        <h1 className="min-w-0 flex-1 text-xl sm:text-2xl md:text-3xl font-bold truncate text-[var(--color-foreground)]" title={t("roles.title")}>
          {t("roles.title")}
        </h1>
        <button
          type="button"
          onClick={() => {
            resetForm();
            setShowCreateModal(true);
          }}
          disabled={actionLoading}
          className="ml-auto shrink-0 bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] px-3 py-2 rounded text-xs sm:text-sm whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {t("roles.newUser")}
        </button>
      </div>

      {error && (
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] p-4 rounded mb-4">{error}</div>
      )}

      {loading ? (
        <div className="text-[var(--color-foreground)]">{t("common.loading")}</div>
      ) : (
        <>
          {/* Asztop: táblázat – Státusz, Szerepkör, Név, Email, Létrehozva, Műveletek (ikonok) */}
          <div className="hidden md:block bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg overflow-hidden">
            <table className="w-full">
              <thead className="bg-[var(--color-table-head)]">
                <tr>
                  <th className="p-3 text-left text-[var(--color-foreground)]">{t("roles.tableStatus")}</th>
                  <th className="p-3 text-left text-[var(--color-foreground)]">{t("roles.tableRole")}</th>
                  <th className="p-3 text-left text-[var(--color-foreground)]">{t("roles.tableName")}</th>
                  <th className="p-3 text-left text-[var(--color-foreground)]">{t("roles.tableEmail")}</th>
                  <th className="p-3 text-left text-[var(--color-foreground)]">{t("roles.tableCreated")}</th>
                  <th className="p-3 text-right text-[var(--color-foreground)]">{t("roles.tableActions")}</th>
                </tr>
              </thead>
              <tbody>
                {sortedUsers.map((user) => (
                  <tr key={user.id} className="border-t border-[var(--color-border)]">
                    <td className="p-3">
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          user.is_active
                            ? "bg-[var(--color-primary)] text-[var(--color-on-primary)]"
                            : user.pending_registration
                              ? "bg-amber-100 dark:bg-amber-900/40 text-amber-900 dark:text-amber-200"
                              : "bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300"
                        }`}
                      >
                        {user.is_active
                          ? t("roles.statusActive")
                          : user.pending_registration
                            ? t("roles.statusPending")
                            : t("roles.statusInactive")}
                      </span>
                    </td>
                    <td className="p-3">
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          user.role === "owner"
                            ? "bg-amber-600 text-white"
                            : user.role === "admin"
                              ? "bg-[var(--color-primary)] text-[var(--color-on-primary)]"
                              : "bg-gray-200 dark:bg-gray-600 text-gray-800 dark:text-gray-200"
                        }`}
                      >
                        {user.role === "owner" ? t("roles.roleOwner") : user.role === "admin" ? t("roles.roleAdmin") : t("roles.roleUser")}
                      </span>
                    </td>
                    <td className={`p-3 ${!user.is_active ? "text-[var(--color-inactive)]" : "text-[var(--color-foreground)]"}`}>{user.name || "—"}</td>
                    <td className={`p-3 ${!user.is_active ? "text-[var(--color-inactive)]" : "text-[var(--color-foreground)]"}`}>{user.email}</td>
                    <td className={`p-3 text-sm ${!user.is_active ? "text-[var(--color-inactive)]" : "text-[var(--color-muted)]"}`}>
                      {user.created_at ? new Date(user.created_at).toLocaleDateString(dateLocale) : "—"}
                    </td>
                    <td className="p-3">
                      <div className="flex flex-wrap gap-2 justify-end items-center">
                        {user.id !== currentUser?.id && user.role !== "owner" && (
                          <button
                            type="button"
                            onClick={() => setDeleteConfirmUser(user)}
                            disabled={actionLoading}
                            className="p-2 rounded text-white bg-red-500 hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed mr-8"
                            title={t("common.delete")}
                            aria-label={t("common.delete")}
                          >
                            <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                          </button>
                        )}
                        {user.role !== "owner" && user.id !== currentUser?.id && (
                          <button
                            type="button"
                            onClick={() => setUserForKbModal(user)}
                            disabled={actionLoading}
                            className="p-2 rounded text-[var(--color-foreground)] bg-[var(--color-card)] border border-[var(--color-border)] hover:bg-[var(--color-button-hover)] disabled:opacity-50 disabled:cursor-not-allowed"
                            title={t("kb.actionPermissions")}
                            aria-label={t("kb.actionPermissions")}
                          >
                            <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>
                          </button>
                        )}
                        {user.pending_registration && user.role !== "owner" && (
                          <button
                            type="button"
                            onClick={() => setResendConfirmUser(user)}
                            disabled={actionLoading}
                            className="p-2 rounded text-[var(--color-foreground)] bg-[var(--color-card)] border border-[var(--color-border)] hover:bg-[var(--color-button-hover)] disabled:opacity-50 disabled:cursor-not-allowed"
                            title={t("roles.resendInvite")}
                            aria-label={t("roles.resendInvite")}
                          >
                            <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
                          </button>
                        )}
                        {user.role === "owner" && currentUser?.role !== "owner" && (
                          <span className="text-[var(--color-muted)] text-xs px-1" title={t("roles.ownerOnlyEdit")}>{t("roles.ownerOnlyEdit")}</span>
                        )}
                        {!(user.role === "owner" && currentUser?.role !== "owner") && (
                          <button
                            type="button"
                            onClick={() => openEditModal(user)}
                            disabled={actionLoading}
                            className="p-2 rounded text-[var(--color-foreground)] bg-[var(--color-card)] border border-[var(--color-border)] hover:bg-[var(--color-button-hover)] disabled:opacity-50 disabled:cursor-not-allowed"
                            title={t("common.edit")}
                            aria-label={t("common.edit")}
                          >
                            <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Keskeny: kártyák */}
          <div className="md:hidden space-y-3">
            {sortedUsers.map((user) => (
              <div key={user.id} className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg p-4 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`px-2 py-1 rounded text-xs ${
                      user.is_active
                        ? "bg-[var(--color-primary)] text-[var(--color-on-primary)]"
                        : user.pending_registration
                          ? "bg-amber-100 dark:bg-amber-900/40 text-amber-900 dark:text-amber-200"
                          : "bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300"
                    }`}
                  >
                    {user.is_active ? t("roles.statusActive") : user.pending_registration ? t("roles.statusPending") : t("roles.statusInactive")}
                  </span>
                  <span
                    className={`px-2 py-1 rounded text-xs ${
                      user.role === "owner" ? "bg-amber-600 text-white" : user.role === "admin" ? "bg-[var(--color-primary)] text-[var(--color-on-primary)]" : "bg-gray-200 dark:bg-gray-600 text-gray-800 dark:text-gray-200"
                    }`}
                  >
                    {user.role === "owner" ? t("roles.roleOwner") : user.role === "admin" ? t("roles.roleAdmin") : t("roles.roleUser")}
                  </span>
                  <span className={`ml-auto text-xs shrink-0 ${!user.is_active ? "text-[var(--color-inactive)]" : "text-[var(--color-muted)]"}`}>{user.created_at ? new Date(user.created_at).toLocaleDateString(dateLocale) : "—"}</span>
                </div>
                <div className="flex items-center gap-2 min-w-0">
                  <div className={`font-medium min-w-0 truncate ${!user.is_active ? "text-[var(--color-inactive)]" : "text-[var(--color-foreground)]"}`}>{user.name || "—"}</div>
                  <div className="flex gap-2 shrink-0 ml-auto items-center">
                    {user.id !== currentUser?.id && user.role !== "owner" && (
                      <button
                        type="button"
                        onClick={() => setDeleteConfirmUser(user)}
                        disabled={actionLoading}
                        className="p-2 rounded text-white bg-red-500 hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed mr-8"
                        title={t("common.delete")}
                        aria-label={t("common.delete")}
                      >
                        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                      </button>
                    )}
                    {user.role !== "owner" && user.id !== currentUser?.id && (
                      <button
                        type="button"
                        onClick={() => setUserForKbModal(user)}
                        disabled={actionLoading}
                        className="p-2 rounded text-[var(--color-foreground)] bg-[var(--color-card)] border border-[var(--color-border)] hover:bg-[var(--color-button-hover)] disabled:opacity-50 disabled:cursor-not-allowed"
                        title={t("kb.actionPermissions")}
                        aria-label={t("kb.actionPermissions")}
                      >
                        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>
                      </button>
                    )}
                    {user.pending_registration && user.role !== "owner" && (
                      <button
                        type="button"
                        onClick={() => setResendConfirmUser(user)}
                        disabled={actionLoading}
                        className="p-2 rounded text-[var(--color-foreground)] bg-[var(--color-card)] border border-[var(--color-border)] hover:bg-[var(--color-button-hover)] disabled:opacity-50 disabled:cursor-not-allowed"
                        title={t("roles.resendInvite")}
                        aria-label={t("roles.resendInvite")}
                      >
                        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
                      </button>
                    )}
                    {user.role === "owner" && currentUser?.role !== "owner" && (
                      <span className="text-[var(--color-muted)] text-xs">{t("roles.ownerOnlyEdit")}</span>
                    )}
                    {!(user.role === "owner" && currentUser?.role !== "owner") && (
                      <button
                        type="button"
                        onClick={() => openEditModal(user)}
                        disabled={actionLoading}
                        className="p-2 rounded text-[var(--color-foreground)] bg-[var(--color-card)] border border-[var(--color-border)] hover:bg-[var(--color-button-hover)] disabled:opacity-50 disabled:cursor-not-allowed"
                        title={t("common.edit")}
                        aria-label={t("common.edit")}
                      >
                        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                      </button>
                    )}
                  </div>
                </div>
                <div className={`text-sm break-all ${!user.is_active ? "text-[var(--color-inactive)]" : "text-[var(--color-foreground)]"}`}>{user.email}</div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-6 rounded-lg w-96 shadow-lg">
            <h2 className="text-2xl font-bold mb-4 text-[var(--color-foreground)]">{t("roles.modalNewTitle")}</h2>
            <p className="text-sm text-[var(--color-muted)] mb-4">{t("roles.modalNewHint")}</p>
            {createFormError && (
              <div className="mb-4 p-3 rounded bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm">
                {createFormError}
              </div>
            )}
            <div className="space-y-4">
              <div>
                <label className="block mb-1 text-[var(--color-label)]">{t("roles.labelName")}{t("common.required")}</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => {
                    setFormData({ ...formData, name: e.target.value });
                    if (createFormError) setCreateFormError(null);
                  }}
                  className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded"
                  placeholder={t("roles.placeholderName")}
                  maxLength={100}
                  required
                />
              </div>
              <div>
                <label className="block mb-1 text-[var(--color-label)]">{t("roles.labelEmail")}{t("common.required")}</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => {
                    setFormData({ ...formData, email: e.target.value });
                    if (createFormError) setCreateFormError(null);
                  }}
                  className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded"
                  placeholder={t("roles.placeholderInviteEmail")}
                  maxLength={100}
                  required
                />
              </div>
              <div>
                <label className="block mb-1 text-[var(--color-label)]">{t("roles.labelRole")}</label>
                <select
                  value={formData.role}
                  onChange={(e) =>
                    setFormData({ ...formData, role: e.target.value as "user" | "admin" })
                  }
                  className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded"
                >
                  <option value="user">{t("roles.roleUser")}</option>
                  <option value="admin">{t("roles.roleAdmin")}</option>
                </select>
              </div>
            </div>
            <div className="flex gap-2 mt-6 justify-end">
              <button
                type="button"
                onClick={() => {
                  setShowCreateModal(false);
                  resetForm();
                  setCreateFormError(null);
                }}
                disabled={actionLoading}
                className="bg-[var(--color-card)] hover:bg-[var(--color-button-hover)] text-[var(--color-foreground)] border border-[var(--color-border)] px-4 py-2 rounded disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                onClick={handleCreate}
                disabled={actionLoading}
                className="bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] px-4 py-2 rounded disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {actionLoading ? t("common.loading") : t("common.create")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editingUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-6 rounded-lg w-96 shadow-lg">
            <h2 className="text-2xl font-bold mb-4 text-[var(--color-foreground)]">{t("roles.modalEditTitle")}</h2>
            {editFormError && (
              <div className="mb-4 p-3 rounded bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm">
                {editFormError}
              </div>
            )}
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <label htmlFor="edit-active-toggle" className="text-[var(--color-label)] font-medium cursor-pointer">
                  {t("roles.labelActive")}
                </label>
                <button
                  id="edit-active-toggle"
                  type="button"
                  role="switch"
                  aria-checked={formData.is_active}
                  disabled={editingUser.role === "owner" || editingUser.pending_registration === true}
                  onClick={() =>
                    (editingUser.role === "owner" || editingUser.pending_registration)
                      ? undefined
                      : setFormData({ ...formData, is_active: !formData.is_active })
                  }
                  className={`
                    relative inline-flex h-6 w-11 shrink-0 rounded-full p-0.5
                    transition-colors duration-200 ease-in-out
                    focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-neutral-600
                    disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none
                    ${formData.is_active ? "bg-[var(--color-primary)]" : "bg-[var(--color-border)]"}
                  `}
                >
                  <span
                    className={`
                      inline-block h-5 w-5 rounded-full bg-white shadow-sm
                      ring-0 transform transition-transform duration-200 ease-in-out
                      ${formData.is_active ? "translate-x-5" : "translate-x-0"}
                    `}
                    aria-hidden
                  />
                </button>
              </div>
              <div>
                <label className="block mb-1 text-[var(--color-label)]">{t("roles.labelName")}{t("common.required")}</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => {
                    setFormData({ ...formData, name: e.target.value });
                    if (editFormError) setEditFormError(null);
                  }}
                  className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded"
                  placeholder={t("roles.placeholderName")}
                  maxLength={100}
                  required
                />
              </div>
              <div>
                <label className="block mb-1 text-[var(--color-label)]">{t("roles.labelEmail")}{!isOwner(editingUser) && editingUser.id !== currentUser?.id ? t("common.required") : ""}</label>
                {isOwner(editingUser) ? (
                  <p className="text-[var(--color-foreground)] bg-[var(--color-table-head)] border border-[var(--color-border)] p-2 rounded text-sm">
                    {editingUser.email}
                  </p>
                ) : (
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => {
                      setFormData({ ...formData, email: e.target.value });
                      if (editFormError) setEditFormError(null);
                    }}
                    className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded"
                    placeholder={t("roles.placeholderEmail")}
                    maxLength={100}
                    required={editingUser.id !== currentUser?.id}
                  />
                )}
              </div>
              <div>
                <label className="block mb-1 text-[var(--color-label)]">{t("roles.labelRole")}</label>
                {isOwner(editingUser) ? (
                  <p className="text-[var(--color-foreground)] bg-[var(--color-table-head)] border border-[var(--color-border)] p-2 rounded text-sm">
                    {t("roles.roleOwner")}
                    <span className="block text-xs text-[var(--color-muted)] mt-1">{t("roles.ownerOnlyName")}</span>
                  </p>
                ) : editingUser.id === currentUser?.id ? (
                  <p className="text-[var(--color-foreground)] bg-[var(--color-table-head)] border border-[var(--color-border)] p-2 rounded text-sm">
                    {editingUser.role === "owner" ? t("roles.roleOwner") : editingUser.role}
                    <span className="block text-xs text-[var(--color-muted)] mt-1">{t("roles.ownRoleNoEdit")}</span>
                  </p>
                ) : (
                  <select
                    value={formData.role}
                    onChange={(e) =>
                      setFormData({ ...formData, role: e.target.value as "user" | "admin" })
                    }
                    className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded"
                  >
                    <option value="user">{t("roles.roleUser")}</option>
                    <option value="admin">{t("roles.roleAdmin")}</option>
                  </select>
                )}
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button
                type="button"
                onClick={() => {
                  setEditingUser(null);
                  resetForm();
                  setEditFormError(null);
                }}
                disabled={actionLoading}
                className="px-4 py-2 rounded text-[var(--color-foreground)] hover:bg-[var(--color-button-hover)] bg-[var(--color-card)] border border-[var(--color-border)] focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                onClick={handleUpdate}
                disabled={actionLoading}
                className="px-4 py-2 rounded bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {actionLoading ? t("common.loading") : t("common.save")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirm */}
      {deleteConfirmUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-6 rounded-lg w-96 shadow-lg">
            <p className="text-[var(--color-foreground)] mb-6">{t("roles.confirmDelete")}</p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeleteConfirmUser(null)}
                disabled={actionLoading}
                className="px-4 py-2 rounded text-[var(--color-foreground)] hover:bg-[var(--color-button-hover)] bg-[var(--color-card)] border border-[var(--color-border)] focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                onClick={() => deleteConfirmUser && handleDelete(deleteConfirmUser.id)}
                disabled={actionLoading}
                className="px-4 py-2 rounded bg-red-500 hover:bg-red-600 text-white focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {actionLoading ? t("common.loading") : t("common.delete")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* User KB access modal (tudástár elérhetőség) */}
      {userForKbModal && (
        <UserKbAccessModal
          user={userForKbModal}
          kbList={kbList}
          onClose={() => setUserForKbModal(null)}
        />
      )}

      {/* Resend invite confirm */}
      {resendConfirmUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-6 rounded-lg w-96 shadow-lg">
            <p className="text-[var(--color-foreground)] mb-6">{t("roles.confirmResend")}</p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setResendConfirmUser(null)}
                disabled={actionLoading}
                className="px-4 py-2 rounded text-[var(--color-foreground)] hover:bg-[var(--color-button-hover)] bg-[var(--color-card)] border border-[var(--color-border)] focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                onClick={() => resendConfirmUser && handleResendInvite(resendConfirmUser.id)}
                disabled={actionLoading}
                className="px-4 py-2 rounded bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {actionLoading ? t("common.loading") : t("common.send")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
