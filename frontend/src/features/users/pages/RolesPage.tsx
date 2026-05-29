import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import {
  useUsers,
  useCreateUserMutation,
  useUpdateUserMutation,
  useDeleteUserMutation,
  useResendInviteMutation,
} from "../hooks/useUsers";
import { useKbList } from "../../knowledge-base/hooks/useKb";
import UserKbAccessModal from "../components/UserKbAccessModal";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import Alert from "../../../components/ui/Alert";
import RolesHeader from "../components/RolesHeader";
import UserConfirmModal from "../components/UserConfirmModal";
import UserCreateModal from "../components/UserCreateModal";
import UserEditModal from "../components/UserEditModal";
import UserRoleList from "../components/UserRoleList";
import type { RoleFormData, RoleUser } from "../components/rolesTypes";

type User = RoleUser;
const LIST_PAGE_SIZE = 10;

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
  const [formData, setFormData] = useState<RoleFormData>({
    email: "",
    name: "",
    role: "user" as "user" | "admin",
    is_active: true,
  });

  /** Várakozó meghívók, aktív userek/adminok, saját user, owner, inaktívak, majd töröltek; csoporton belül névsor. */
  const sortedUsers = useMemo(() => {
    const nameKey = (u: User) => (u.name || u.email || "").trim().toLowerCase();
    const groupKey = (u: User) => {
      if (u.deleted_at) return 8;
      if (!u.is_active) return 7;
      if (u.pending_registration) return u.role === "admin" ? 2 : 1;
      if (u.id === currentUser?.id) return 5;
      if (u.role === "admin") return 4;
      if (u.role === "owner") return 6;
      return 3;
    };
    return [...users].sort((a, b) => {
      const groupDiff = groupKey(a) - groupKey(b);
      if (groupDiff !== 0) return groupDiff;
      return nameKey(a).localeCompare(nameKey(b));
    });
  }, [currentUser?.id, users]);
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
    const canEditEmail = editingUser.role !== "owner";

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

    const payload: { id: number; name: string; email?: string; role?: string } = {
      id: editingUser.id,
      name: nameTrim,
    };
    if (editingUser.role !== "owner") {
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

  const handleToggleActive = (user: User) => {
    if (
      user.id === currentUser?.id ||
      user.role === "owner"
    ) return;
    updateUserMutation.mutate(
      {
        id: user.id,
        name: user.name ?? "",
        is_active: !user.is_active,
      },
      {
        onSuccess: () => toast.success(t("profile.saved")),
        onError: (err: unknown) => toast.error(getApiErrorMessage(err) ?? t("roles.errorUpdate")),
      }
    );
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
      <div className="min-h-[70vh] flex items-center justify-center bg-[var(--color-background)] p-6 text-[var(--color-foreground)]">
        <div className="text-center">
          <p className="text-5xl font-semibold">404</p>
          <p className="mt-3 text-sm text-[var(--color-muted)]">{t("roles.noPermission")}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="app-page">
      <div className="app-page-container">
        <RolesHeader
          t={t}
          actionLoading={actionLoading}
          onCreate={() => {
            resetForm();
            setShowCreateModal(true);
          }}
        />

        {error && (
          <Alert tone="error">{error}</Alert>
        )}

        {loading ? (
          <div className="text-[var(--color-foreground)]">{t("common.loading")}</div>
        ) : (
          <UserRoleList
            users={displayedUsers}
            currentUser={currentUser}
            actionLoading={actionLoading}
            loadMoreRef={loadMoreRef}
            t={t}
            onDelete={setDeleteConfirmUser}
            onKbPermissions={setUserForKbModal}
            onEdit={openEditModal}
            onResendInvite={setResendConfirmUser}
            onToggleActive={handleToggleActive}
          />
        )}
      </div>

      <UserCreateModal
        open={showCreateModal}
        formData={formData}
        formError={createFormError}
        actionLoading={actionLoading}
        t={t}
        setFormData={setFormData}
        clearFormError={() => createFormError && setCreateFormError(null)}
        onClose={() => {
          setShowCreateModal(false);
          resetForm();
          setCreateFormError(null);
        }}
        onCreate={handleCreate}
      />

      <UserEditModal
        user={editingUser}
        currentUserId={currentUser?.id}
        formData={formData}
        formError={editFormError}
        actionLoading={actionLoading}
        t={t}
        setFormData={setFormData}
        clearFormError={() => editFormError && setEditFormError(null)}
        onClose={() => {
          setEditingUser(null);
          resetForm();
          setEditFormError(null);
        }}
        onSave={handleUpdate}
      />

      <UserConfirmModal
        open={Boolean(deleteConfirmUser)}
        title={t("common.delete")}
        description={t("roles.confirmDelete")}
        confirmLabel={t("common.delete")}
        actionLoading={actionLoading}
        danger
        t={t}
        onClose={() => setDeleteConfirmUser(null)}
        onConfirm={() => deleteConfirmUser && handleDelete(deleteConfirmUser.id)}
      />

      {/* User KB access modal (tudástár elérhetőség) */}
      {userForKbModal && (
        <UserKbAccessModal
          user={userForKbModal}
          kbList={kbList}
          onClose={() => setUserForKbModal(null)}
        />
      )}

      <UserConfirmModal
        open={Boolean(resendConfirmUser)}
        title={t("roles.resendInvite")}
        description={t("roles.confirmResend")}
        confirmLabel={t("common.send")}
        actionLoading={actionLoading}
        t={t}
        onClose={() => setResendConfirmUser(null)}
        onConfirm={() => resendConfirmUser && handleResendInvite(resendConfirmUser.id)}
      />
    </div>
  );
}
