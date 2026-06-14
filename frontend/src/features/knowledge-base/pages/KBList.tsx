import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { SavedModal } from "../../../components/SavedModal";
import Alert from "../../../components/ui/Alert";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { useBillingOverview } from "../../billing/hooks/useBilling";
import { useUsers } from "../../users/hooks/useUsers";
import KBCreateModal from "../components/list/KBCreateModal";
import KBDeleteConfirmModal from "../components/list/KBDeleteConfirmModal";
import KBLimitModal from "../components/list/KBLimitModal";
import KBListHeader from "../components/list/KBListHeader";
import KBListSummary from "../components/list/KBListSummary";
import KBListTable from "../components/list/KBListTable";
import KBSettingsModal from "../components/list/KBSettingsModal";
import {
  KB_NAME_MAX_LENGTH,
  PERM_NONE,
  isDeletedKb,
  metricValue,
  nameMaxLengthMessage,
  type KbFormData,
} from "../components/list/kbListUtils";
import {
  useCreateKbMutation,
  useDeleteKbMutation,
  useKbList,
  useKbPermissions,
  useSetKbPermissionsMutation,
  useUpdateKbMutation,
  type KbItem,
} from "../hooks/useKb";

const LIST_PAGE_SIZE = 10;

export default function KBList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const currentUserId = useAuthStore((state) => state.user?.id);
  const canManage = useAuthStore((state) => state.user?.role === "admin" || state.user?.role === "owner");
  const isOwner = useAuthStore((state) => state.user?.role === "owner");
  const { data: items = [], isLoading: loading, error: listError } = useKbList({ refetchOnMount: "always" });
  const { data: users = [] } = useUsers({ enabled: canManage });
  const { data: billingOverview, isPending: billingOverviewPending } = useBillingOverview({
    enabled: isOwner,
    refetchOnMount: "always",
  });

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createFormError, setCreateFormError] = useState<string | null>(null);
  const [editFormError, setEditFormError] = useState<string | null>(null);
  const [settingsKb, setSettingsKb] = useState<KbItem | null>(null);
  const [piiDepersonalizationEnabled, setPiiDepersonalizationEnabled] = useState(true);
  const [publicEnabled, setPublicEnabled] = useState(false);
  const [deleteConfirmKb, setDeleteConfirmKb] = useState<KbItem | null>(null);
  const [deleteTypeName, setDeleteTypeName] = useState("");
  const [savedModalOpen, setSavedModalOpen] = useState(false);
  const [showKbLimitModal, setShowKbLimitModal] = useState(false);
  const [visibleCount, setVisibleCount] = useState(LIST_PAGE_SIZE);
  const [formData, setFormData] = useState<KbFormData>({ name: "", description: "" });
  const [createPermissions, setCreatePermissions] = useState<Record<number, string>>({});
  const [settingsPermissions, setSettingsPermissions] = useState<Record<number, string>>({});
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const settingsPermsSyncedUuid = useRef<string | null>(null);

  const createKbMutation = useCreateKbMutation();
  const updateKbMutation = useUpdateKbMutation();
  const deleteKbMutation = useDeleteKbMutation();
  const setPermissionsMutation = useSetKbPermissionsMutation();
  const { data: settingsPermsList = [], isLoading: settingsPermsLoading } = useKbPermissions(settingsKb?.uuid ?? undefined, {
    enabled: Boolean(settingsKb),
  });

  const paymentWarning = (billingOverview?.payment_warning as Record<string, unknown> | null | undefined) ?? null;
  const billingRestricted =
    String((billingOverview?.subscription as Record<string, unknown> | undefined)?.status ?? "").toLowerCase() === "restricted" ||
    paymentWarning?.is_expired === true;
  const canDeleteKb = isOwner;
  const activeKnowledgeBaseCount = useMemo(() => items.filter((kb) => !isDeletedKb(kb)).length, [items]);
  const visibleItems = useMemo(
    () =>
      [...items]
        .filter((kb) => !isDeletedKb(kb) || metricValue(kb, "training_char_count") > 0)
        .sort((left, right) => Number(isDeletedKb(left)) - Number(isDeletedKb(right))),
    [items]
  );
  const displayedItems = useMemo(() => visibleItems.slice(0, visibleCount), [visibleItems, visibleCount]);
  const kbPackageLimitBlocked = useMemo(() => {
    if (!isOwner || billingOverviewPending || !billingOverview) return false;
    const kbMaxRaw = billingOverview.limits?.knowledge_bases;
    const kbMax = typeof kbMaxRaw === "number" ? kbMaxRaw : Number.NaN;
    return Number.isFinite(kbMax) && kbMax > 0 && activeKnowledgeBaseCount >= kbMax;
  }, [isOwner, billingOverviewPending, billingOverview, activeKnowledgeBaseCount]);
  const kbLimitDetails = useMemo(() => {
    const kbMaxRaw = billingOverview?.limits?.knowledge_bases;
    return {
      max: typeof kbMaxRaw === "number" ? kbMaxRaw : null,
      used: activeKnowledgeBaseCount,
    };
  }, [billingOverview, activeKnowledgeBaseCount]);
  const actionLoading =
    createKbMutation.isPending || updateKbMutation.isPending || deleteKbMutation.isPending || setPermissionsMutation.isPending;
  const settingsKbIsPublic = publicEnabled;
  const settingsSaveLoading = updateKbMutation.isPending || (!settingsKbIsPublic && setPermissionsMutation.isPending);
  const usersWithPermsCreate = useMemo(
    () =>
      (users as Array<{ id: number; email: string; name?: string | null; role?: string }>)
        .filter((user) => user.id != null && (user.role ?? "user") === "user")
        .map((user) => ({
          id: user.id,
          email: user.email,
          name: user.name ?? null,
          permission: createPermissions[user.id] ?? PERM_NONE,
          role: user.role ?? "user",
        })),
    [users, createPermissions]
  );
  const usersWithPermsSettings = useMemo(
    () =>
      settingsPermsList
        .filter((permission) => permission.role !== "admin")
        .map((permission) => ({
          id: permission.user_id,
          email: permission.email,
          name: permission.name ?? null,
          permission: settingsPermissions[permission.user_id] ?? permission.permission,
          role: permission.role ?? "user",
        })),
    [settingsPermsList, settingsPermissions]
  );
  const error = listError ? (getApiErrorMessage(listError) ?? t("kb.errorLoad")) : null;
  const totalFileBytes = visibleItems.reduce((sum, kb) => sum + metricValue(kb, "file_bytes"), 0);
  const totalDatabaseBytes = visibleItems.reduce((sum, kb) => sum + metricValue(kb, "database_bytes"), 0);
  const totalTrainingChars = visibleItems.reduce((sum, kb) => sum + metricValue(kb, "training_char_count"), 0);
  const totalStorageBytes = visibleItems.reduce((sum, kb) => sum + metricValue(kb, "total_bytes"), 0);

  useEffect(() => {
    setVisibleCount(LIST_PAGE_SIZE);
  }, [visibleItems.length]);

  useEffect(() => {
    const node = loadMoreRef.current;
    if (!node || visibleCount >= visibleItems.length) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisibleCount((count) => Math.min(count + LIST_PAGE_SIZE, visibleItems.length));
        }
      },
      { rootMargin: "320px" }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [visibleCount, visibleItems.length]);

  useEffect(() => {
    if (!settingsKb || settingsPermsList.length === 0) return;
    if (settingsPermsSyncedUuid.current === settingsKb.uuid) return;
    settingsPermsSyncedUuid.current = settingsKb.uuid;
    const next: Record<number, string> = {};
    for (const permission of settingsPermsList) {
      next[permission.user_id] = permission.permission;
    }
    setSettingsPermissions(next);
  }, [settingsKb, settingsPermsList]);

  useEffect(() => {
    const openKbCreate = Boolean((location.state as { openKbCreate?: boolean })?.openKbCreate);
    if (!openKbCreate) return;
    if (isOwner && billingOverviewPending) return;
    navigate(location.pathname, { replace: true, state: {} });
    if (!isOwner) return;
    if (kbPackageLimitBlocked) {
      setShowKbLimitModal(true);
    } else {
      resetForm();
      setShowCreateModal(true);
    }
  }, [location.state, location.pathname, navigate, isOwner, billingOverviewPending, kbPackageLimitBlocked]);

  const resetForm = () => {
    setFormData({ name: "", description: "" });
    setCreatePermissions({});
    setCreateFormError(null);
    setEditFormError(null);
  };

  const openCreateModal = () => {
    if (kbPackageLimitBlocked) {
      setShowKbLimitModal(true);
      return;
    }
    resetForm();
    setShowCreateModal(true);
  };

  const openSettingsModal = (kb: KbItem) => {
    setSettingsKb(kb);
    setSettingsPermissions({});
    setPiiDepersonalizationEnabled(kb.pii_depersonalization_enabled !== false);
    setPublicEnabled(Boolean(kb.public_enabled ?? kb.is_public ?? false));
    settingsPermsSyncedUuid.current = null;
    setEditFormError(null);
    setFormData({ name: kb.name, description: kb.description ?? "" });
  };

  const handleCreate = (event: React.FormEvent) => {
    event.preventDefault();
    const nameTrim = formData.name?.trim() ?? "";
    setCreateFormError(null);
    if (!nameTrim) {
      setCreateFormError(t("common.fieldRequired"));
      return;
    }
    if (nameTrim.length > KB_NAME_MAX_LENGTH) {
      setCreateFormError(nameMaxLengthMessage(t));
      return;
    }
    const permissions = usersWithPermsCreate
      .filter((user) => user.permission && user.permission !== PERM_NONE)
      .map((user) => ({ user_id: user.id, permission: user.permission }));
    createKbMutation.mutate(
      { name: nameTrim, permissions: permissions.length ? permissions : undefined },
      {
        onSuccess: () => {
          setSavedModalOpen(true);
          setShowCreateModal(false);
          resetForm();
        },
        onError: (err: unknown) => toast.error(getApiErrorMessage(err) ?? t("kb.errorCreate")),
      }
    );
  };

  const handleSaveSettings = () => {
    if (!settingsKb) return;
    const nameTrim = formData.name?.trim() ?? "";
    setEditFormError(null);
    if (!nameTrim) {
      setEditFormError(t("common.fieldRequired"));
      return;
    }
    if (nameTrim.length > KB_NAME_MAX_LENGTH) {
      setEditFormError(nameMaxLengthMessage(t));
      return;
    }
    const finishSettingsSave = () => {
      setSavedModalOpen(true);
      setSettingsKb(null);
      resetForm();
    };
    const permissions = usersWithPermsSettings.map((user) => ({ user_id: user.id, permission: user.permission }));
    updateKbMutation.mutate(
      {
        uuid: settingsKb.uuid,
        name: nameTrim,
        description: settingsKb.description?.trim() || undefined,
        pii_depersonalization_enabled: piiDepersonalizationEnabled,
        public_enabled: publicEnabled,
      },
      {
        onSuccess: () => {
          if (settingsKbIsPublic) {
            finishSettingsSave();
            return;
          }
          setPermissionsMutation.mutate(
            { uuid: settingsKb.uuid, permissions },
            {
              onSuccess: finishSettingsSave,
              onError: (err: unknown) => toast.error(getApiErrorMessage(err) ?? t("kb.errorPermissions")),
            }
          );
        },
        onError: (err: unknown) => toast.error(getApiErrorMessage(err) ?? t("kb.errorUpdate")),
      }
    );
  };

  const handleDelete = () => {
    if (!deleteConfirmKb) return;
    if (!canDeleteKb) {
      toast.error(t("kb.errorDeleteNotAllowed"));
      return;
    }
    if (deleteTypeName.trim() !== deleteConfirmKb.name) {
      toast.error(t("kb.deleteConfirmMismatch"));
      return;
    }
    deleteKbMutation.mutate(
      { uuid: deleteConfirmKb.uuid, confirm_name: deleteTypeName.trim() },
      {
        onSuccess: () => {
          toast.success(t("common.delete") + " – OK");
          setDeleteConfirmKb(null);
          setDeleteTypeName("");
        },
        onError: (err: unknown) => toast.error(getApiErrorMessage(err) ?? t("kb.errorDelete")),
      }
    );
  };

  if (loading) {
    return <div className="app-page text-[var(--color-foreground)]">{t("common.loading")}</div>;
  }

  return (
    <div className="app-page">
      <div className="app-page-container">
        <KBListHeader
          isOwner={isOwner}
          billingRestricted={billingRestricted}
          actionLoading={actionLoading}
          billingOverviewPending={billingOverviewPending}
          t={t}
          onOpenTraffic={() => navigate("/admin/forgalom")}
          onCreate={openCreateModal}
        />
        {error ? <Alert tone="error">{error}</Alert> : null}
        <KBListSummary
          totalKnowledgeBases={activeKnowledgeBaseCount}
          totalStorageBytes={totalStorageBytes}
          totalFileBytes={totalFileBytes}
          totalDatabaseBytes={totalDatabaseBytes}
          totalTrainingChars={totalTrainingChars}
          t={t}
        />
        <KBListTable
          items={displayedItems}
          canManage={canManage}
          canDeleteKb={canDeleteKb}
          billingRestricted={billingRestricted}
          actionLoading={actionLoading}
          loadMoreRef={loadMoreRef}
          t={t}
          onTrainingLog={(kb) => navigate(`/kb/monitor/${kb.uuid}`)}
          onSettings={openSettingsModal}
          onDelete={(kb) => {
            setDeleteConfirmKb(kb);
            setDeleteTypeName("");
          }}
        />
      </div>

      <KBCreateModal
        open={showCreateModal}
        formData={formData}
        formError={createFormError}
        canManage={canManage}
        actionLoading={actionLoading}
        usersWithPerms={usersWithPermsCreate}
        currentUserId={currentUserId}
        t={t}
        setFormData={setFormData}
        clearFormError={() => createFormError && setCreateFormError(null)}
        onPermissionChange={(userId, permission) => setCreatePermissions((prev) => ({ ...prev, [userId]: permission }))}
        onClose={() => {
          setShowCreateModal(false);
          resetForm();
        }}
        onSubmit={handleCreate}
      />
      <KBSettingsModal
        kb={settingsKb}
        formData={formData}
        formError={editFormError}
        piiDepersonalizationEnabled={piiDepersonalizationEnabled}
        isPublic={settingsKbIsPublic}
        publicEnabled={publicEnabled}
        settingsPermsLoading={settingsPermsLoading}
        settingsSaveLoading={settingsSaveLoading}
        actionLoading={actionLoading}
        usersWithPerms={usersWithPermsSettings}
        currentUserId={currentUserId}
        t={t}
        setFormData={setFormData}
        setPiiDepersonalizationEnabled={setPiiDepersonalizationEnabled}
        setPublicEnabled={setPublicEnabled}
        clearFormError={() => editFormError && setEditFormError(null)}
        onPermissionChange={(userId, permission) => setSettingsPermissions((prev) => ({ ...prev, [userId]: permission }))}
        onClose={() => {
          setSettingsKb(null);
          resetForm();
        }}
        onSave={handleSaveSettings}
      />
      <KBLimitModal
        open={showKbLimitModal}
        max={kbLimitDetails.max}
        used={kbLimitDetails.used}
        t={t}
        onClose={() => setShowKbLimitModal(false)}
        onViewPackages={() => {
          setShowKbLimitModal(false);
          navigate("/admin/pricing");
        }}
      />
      <SavedModal open={savedModalOpen} onClose={() => setSavedModalOpen(false)} />
      {canDeleteKb ? (
        <KBDeleteConfirmModal
          kb={deleteConfirmKb}
          deleteTypeName={deleteTypeName}
          actionLoading={actionLoading}
          t={t}
          setDeleteTypeName={setDeleteTypeName}
          onClose={() => {
            setDeleteConfirmKb(null);
            setDeleteTypeName("");
          }}
          onDelete={handleDelete}
        />
      ) : null}
    </div>
  );
}
