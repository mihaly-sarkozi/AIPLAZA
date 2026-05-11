import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { useTranslation } from "../../../i18n";
import { SavedModal } from "../../../components/SavedModal";
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
import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../components/ui/Modal";
import PageHeader from "../../../components/ui/PageHeader";

type User = UserListItem & { pending_registration?: boolean };
const LIST_PAGE_SIZE = 10;

function isDeletedUser(user: User): boolean {
  return Boolean(user.deleted_at);
}

function getStatusClasses(user: User): string {
  if (isDeletedUser(user)) return "bg-[var(--color-danger-text)] text-white";
  if (user.is_active) return "bg-[var(--color-success-text)] text-white";
  if (user.pending_registration) return "bg-amber-500 text-white";
  return "bg-slate-500 text-white";
}

export default function RolesPage() {
  const { t } = useTranslation();
  const { user: currentUser, setUser: setCurrentUser } = useAuthStore();
  const canManage = currentUser?.role === "admin" || currentUser?.role === "owner";
  const { data: usersData, isLoading: loading, error: usersError } = useUsers({ enabled: canManage });
  const users = useMemo(() => (usersData ?? []) as User[], [usersData]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createFormError, setCreateFormError] = useState<string | null>(null);
  const [editFormError, setEditFormError] = useState<string | null>(null);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [deleteConfirmUser, setDeleteConfirmUser] = useState<User | null>(null);
  const [resendConfirmUser, setResendConfirmUser] = useState<User | null>(null);
  const [userForKbModal, setUserForKbModal] = useState<User | null>(null);
  const [savedModalOpen, setSavedModalOpen] = useState(false);
  const [visibleCount, setVisibleCount] = useState(LIST_PAGE_SIZE);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

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
  const displayedUsers = useMemo(() => sortedUsers.slice(0, visibleCount), [sortedUsers, visibleCount]);

  useEffect(() => {
    setVisibleCount(LIST_PAGE_SIZE);
  }, [sortedUsers.length]);

  useEffect(() => {
    const node = loadMoreRef.current;
    if (!node || visibleCount >= sortedUsers.length) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisibleCount((count) => Math.min(count + LIST_PAGE_SIZE, sortedUsers.length));
        }
      },
      { rootMargin: "320px" }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [visibleCount, sortedUsers.length]);
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
          setSavedModalOpen(true);
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
      onSuccess: (updatedUser) => {
        if (currentUser && updatedUser.id === currentUser.id) {
          setCurrentUser({
            ...currentUser,
            name: updatedUser.name ?? currentUser.name,
            email: updatedUser.email ?? currentUser.email,
            role: (updatedUser.role as "user" | "admin" | "owner") ?? currentUser.role,
          });
        }
        setSavedModalOpen(true);
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
    <div className="app-page">
      <div className="app-page-container">
        <PageHeader
          eyebrow={t("roles.teamLabel")}
          title={t("roles.title")}
          description={t("roles.pageIntro")}
          actions={
            <Button
              onClick={() => {
                resetForm();
                setShowCreateModal(true);
              }}
              disabled={actionLoading}
            >
              {t("roles.newUser")}
            </Button>
          }
        />

        {error && (
          <Alert tone="error">{error}</Alert>
        )}

        {loading ? (
          <div className="text-[var(--color-foreground)]">{t("common.loading")}</div>
        ) : (
          <section>
            <div className="app-table-wrap">
              <div className="app-table-head hidden grid-cols-[1.3fr_0.9fr_1.6fr_1.5fr] gap-4 !bg-[#efefef] px-5 py-3 text-sm font-medium !text-[var(--color-foreground)] md:grid">
                <div>{t("roles.tableName")}</div>
                <div>{t("roles.tableRole")}</div>
                <div>{t("roles.tableEmail")}</div>
                <div>{t("roles.tableActions")}</div>
              </div>

              <div className="divide-y divide-[var(--color-border)]">
                {displayedUsers.map((user) => {
                const statusLabel = isDeletedUser(user)
                  ? t("roles.statusDeleted")
                  : user.is_active
                    ? t("roles.statusActive")
                    : user.pending_registration
                      ? t("roles.statusPending")
                      : t("roles.statusInactive");
                const roleLabel =
                  user.role === "owner" ? t("roles.roleOwner") : user.role === "admin" ? t("roles.roleAdmin") : t("roles.roleUser");
                const displayName = user.name || "—";

                return (
                  <div
                    key={user.id}
                    className="grid gap-3 px-5 py-4 md:grid-cols-[1.3fr_0.9fr_1.6fr_1.5fr] md:items-center md:gap-4"
                  >
                    <div>
                      <p className="text-sm font-medium text-[var(--color-foreground)]">{displayName}</p>
                      <span className={`mt-1 inline-block rounded-lg px-2 py-0.5 text-xs font-medium ${getStatusClasses(user)}`}>
                        {statusLabel}
                      </span>
                    </div>

                    <div className="text-sm text-[var(--color-muted-foreground)]">{roleLabel}</div>

                    <div className="break-all text-sm text-[var(--color-muted)]">{user.email}</div>

                    <div className="grid grid-cols-3 gap-2">
                      {user.id !== currentUser?.id && user.role !== "owner" && (
                        <Button
                          type="button"
                          onClick={() => setDeleteConfirmUser(user)}
                          disabled={actionLoading}
                          variant="danger"
                          title={t("common.delete")}
                          aria-label={t("common.delete")}
                          className="w-full"
                        >
                          {t("common.delete")}
                        </Button>
                      )}
                      {user.role !== "owner" && user.id !== currentUser?.id && (
                        <Button
                          type="button"
                          onClick={() => setUserForKbModal(user)}
                          disabled={actionLoading}
                          variant="secondary"
                          title={t("kb.actionPermissions")}
                          aria-label={t("kb.actionPermissions")}
                          className="w-full"
                        >
                          {t("kb.actionPermissions")}
                        </Button>
                      )}
                      {user.role === "owner" && currentUser?.role !== "owner" ? (
                        <span className="col-span-3 text-xs text-slate-400" title={t("roles.ownerOnlyEdit")}>
                          {t("roles.ownerOnlyEdit")}
                        </span>
                      ) : (
                        <Button
                          type="button"
                          onClick={() => openEditModal(user)}
                          disabled={actionLoading}
                          variant="secondary"
                          title={t("roles.actionSettings")}
                          aria-label={t("roles.actionSettings")}
                          className="w-full"
                        >
                          {t("roles.actionSettings")}
                        </Button>
                      )}
                      {user.pending_registration && user.role !== "owner" && (
                        <Button
                          type="button"
                          onClick={() => setResendConfirmUser(user)}
                          disabled={actionLoading}
                          variant="secondary"
                          title={t("roles.resendInvite")}
                          aria-label={t("roles.resendInvite")}
                          className="col-span-3 w-full !bg-[#efefef] !text-[var(--color-foreground)] hover:!bg-[#e5e5e5]"
                        >
                          {t("roles.resendInvite")}
                        </Button>
                      )}
                    </div>
                  </div>
                );
                })}
              </div>
              <div ref={loadMoreRef} className="h-8" />
            </div>
          </section>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <Modal open={showCreateModal} onClose={() => setShowCreateModal(false)} panelClassName="max-w-md">
            <ModalHeader title={t("roles.modalNewTitle")} description={t("roles.modalNewHint")} />
            {createFormError && (
              <Alert tone="error" className="mb-4">{createFormError}</Alert>
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
            <ModalFooter>
              <Button
                type="button"
                onClick={() => {
                  setShowCreateModal(false);
                  resetForm();
                  setCreateFormError(null);
                }}
                variant="secondary"
                disabled={actionLoading}
              >
                {t("common.cancel")}
              </Button>
              <Button
                type="button"
                onClick={handleCreate}
                disabled={actionLoading}
              >
                {actionLoading ? t("common.loading") : t("common.create")}
              </Button>
            </ModalFooter>
        </Modal>
      )}

      {/* Edit Modal */}
      {editingUser && (
        <Modal open={Boolean(editingUser)} onClose={() => setEditingUser(null)} panelClassName="max-w-md">
            <ModalHeader title={t("roles.modalEditTitle")} />
            {editFormError && (
              <Alert tone="error" className="mb-4">{editFormError}</Alert>
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
            <ModalFooter>
              <Button
                type="button"
                onClick={() => {
                  setEditingUser(null);
                  resetForm();
                  setEditFormError(null);
                }}
                variant="secondary"
                disabled={actionLoading}
              >
                {t("common.cancel")}
              </Button>
              <Button
                type="button"
                onClick={handleUpdate}
                disabled={actionLoading}
              >
                {actionLoading ? t("common.loading") : t("common.save")}
              </Button>
            </ModalFooter>
        </Modal>
      )}

      <SavedModal
        open={savedModalOpen}
        onClose={() => setSavedModalOpen(false)}
      />

      {/* Delete confirm */}
      {deleteConfirmUser && (
        <Modal open={Boolean(deleteConfirmUser)} onClose={() => setDeleteConfirmUser(null)} panelClassName="max-w-md">
            <ModalHeader title={t("common.delete")} description={t("roles.confirmDelete")} />
            <ModalFooter>
              <Button
                type="button"
                onClick={() => setDeleteConfirmUser(null)}
                variant="secondary"
                disabled={actionLoading}
              >
                {t("common.cancel")}
              </Button>
              <Button
                type="button"
                onClick={() => deleteConfirmUser && handleDelete(deleteConfirmUser.id)}
                variant="danger"
                disabled={actionLoading}
              >
                {actionLoading ? t("common.loading") : t("common.delete")}
              </Button>
            </ModalFooter>
        </Modal>
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
        <Modal open={Boolean(resendConfirmUser)} onClose={() => setResendConfirmUser(null)} panelClassName="max-w-md">
            <ModalHeader title={t("roles.resendInvite")} description={t("roles.confirmResend")} />
            <ModalFooter>
              <Button
                type="button"
                onClick={() => setResendConfirmUser(null)}
                variant="secondary"
                disabled={actionLoading}
              >
                {t("common.cancel")}
              </Button>
              <Button
                type="button"
                onClick={() => resendConfirmUser && handleResendInvite(resendConfirmUser.id)}
                disabled={actionLoading}
              >
                {actionLoading ? t("common.loading") : t("common.send")}
              </Button>
            </ModalFooter>
        </Modal>
      )}
    </div>
  );
}
