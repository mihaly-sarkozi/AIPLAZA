import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useTranslation } from "../../../i18n";
import { getKbPermissionsBatch } from "../../knowledge-base/services";
import { useSetKbPermissionsMutation } from "../../knowledge-base/hooks/useKb";
import type { KbItem, KbPermissionItem } from "../../knowledge-base/services";
import type { UserListItem } from "../hooks/useUsers";
import Button from "../../../components/ui/Button";
import Alert from "../../../components/ui/Alert";
import Modal, { ModalFooter, ModalHeader } from "../../../components/ui/Modal";

const PERM_NONE = "none";
const PERM_USE = "use";
const PERM_TRAIN = "train";

type User = UserListItem & { role: string };

interface UserKbAccessModalProps {
  user: User;
  onClose: () => void;
  kbList: KbItem[];
}

export default function UserKbAccessModal({ user, onClose, kbList }: UserKbAccessModalProps) {
  const { t } = useTranslation();
  const [permissionsByKb, setPermissionsByKb] = useState<Record<string, Array<{ user_id: number; permission: string }>>>({});
  const [initialPermissionsByKb, setInitialPermissionsByKb] = useState<Record<string, Array<{ user_id: number; permission: string }>>>({});
  const [isLoadingPermissions, setIsLoadingPermissions] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const setPermissionsMutation = useSetKbPermissionsMutation();
  const actionLoading = isLoadingPermissions || setPermissionsMutation.isPending;

  useEffect(() => {
    let cancelled = false;
    async function loadPermissions() {
      if (!user?.id) {
        setPermissionsByKb({});
        setInitialPermissionsByKb({});
        setIsLoadingPermissions(false);
        return;
      }
      setIsLoadingPermissions(true);
      setLoadError(null);
      const next: Record<string, Array<{ user_id: number; permission: string }>> = {};
      const kbUuids = kbList.map((kb) => kb.uuid).filter(Boolean);
      try {
        const byKb = await getKbPermissionsBatch(kbUuids);
        kbList.forEach((kb) => {
          const rows = (byKb[kb.uuid] || []) as KbPermissionItem[];
          next[kb.uuid] = rows.map((p) => ({ user_id: p.user_id, permission: p.permission }));
        });
      } catch {
        kbList.forEach((kb) => {
          next[kb.uuid] = [];
        });
        if (!cancelled) {
          setLoadError("A jogosultságokat nem sikerült betölteni.");
        }
      }
      if (cancelled) return;
      setPermissionsByKb(next);
      setInitialPermissionsByKb(next);
      setIsLoadingPermissions(false);
    }
    loadPermissions();
    return () => {
      cancelled = true;
    };
  }, [user?.id, kbList]);

  const changedKbUuids = useMemo(() => {
    const normalize = (items: Array<{ user_id: number; permission: string }> = []) =>
      items
        .filter((p) => p.permission && p.permission !== PERM_NONE)
        .map((p) => ({ user_id: p.user_id, permission: p.permission }))
        .sort((a, b) => a.user_id - b.user_id);
    const same = (a: Array<{ user_id: number; permission: string }> = [], b: Array<{ user_id: number; permission: string }> = []) =>
      JSON.stringify(normalize(a)) === JSON.stringify(normalize(b));
    return kbList
      .filter((kb) => !same(permissionsByKb[kb.uuid] ?? [], initialPermissionsByKb[kb.uuid] ?? []))
      .map((kb) => kb.uuid);
  }, [kbList, permissionsByKb, initialPermissionsByKb]);

  const getPermissionForUser = (kbUuid: string) => {
    const list = permissionsByKb[kbUuid] ?? [];
    return list.find((p) => p.user_id === user.id)?.permission ?? PERM_NONE;
  };

  const setPermissionForUser = (kbUuid: string, permission: string) => {
    setPermissionsByKb((prev) => {
      const list = prev[kbUuid] ?? [];
      const filtered = list.filter((p) => p.user_id !== user.id);
      const newList = permission === PERM_NONE ? filtered : [...filtered, { user_id: user.id, permission }];
      return { ...prev, [kbUuid]: newList };
    });
  };

  const handleSave = async () => {
    setSaveError(null);
    if (changedKbUuids.length === 0) {
      onClose();
      return;
    }
    try {
      for (const kbUuid of changedKbUuids) {
        const list = permissionsByKb[kbUuid] ?? [];
        await setPermissionsMutation.mutateAsync({ uuid: kbUuid, permissions: list });
      }
    } catch {
      setSaveError("A mentés közben hiba történt. Ellenőrizd a kapcsolatot, majd próbáld újra.");
      return;
    }
    toast.success(t("profile.saved"));
    onClose();
  };

  const isImplicitKnowledgeManager = user.role === "owner" || user.role === "admin";

  return (
    <Modal open={true} onClose={onClose} panelClassName="max-w-2xl">
        <ModalHeader
          eyebrow={t("nav.knowledgeBase")}
          title={user.name ?? user.email}
          description={t("roles.kbAccessHint")}
        />
        {isLoadingPermissions ? (
          <p className="text-[var(--color-muted)]">{t("common.loading")}</p>
        ) : loadError ? (
          <>
            <Alert tone="error" className="mb-3">{loadError}</Alert>
            <ModalFooter className="mt-4">
              <Button
                type="button"
                onClick={onClose}
                variant="secondary"
              >
                {t("common.cancel")}
              </Button>
            </ModalFooter>
          </>
        ) : (
          <>
            {saveError ? <Alert tone="error" className="mb-3">{saveError}</Alert> : null}
            <div className="border border-[var(--color-border)] rounded overflow-hidden max-h-64 overflow-y-auto">
              <table className="w-full text-sm">
                <tbody>
                  <tr className="border-b border-[var(--color-border)] bg-[var(--color-table-head)]">
                    <td className="p-2 text-xs font-normal text-[var(--color-foreground)] w-[55%]">{t("kb.tableName")}</td>
                    <td className="p-2 text-xs font-normal text-[var(--color-foreground)] text-center">{t("kb.hasAccess")}</td>
                    <td className="p-2 text-xs font-normal text-[var(--color-foreground)] text-center">{t("kb.columnTrainer")}</td>
                  </tr>
                  {kbList.map((kb) => {
                    const perm = getPermissionForUser(kb.uuid);
                    const hasPermission = perm === PERM_USE || perm === PERM_TRAIN;
                    const canTrain = perm === PERM_TRAIN;
                    return (
                      <tr key={kb.uuid} className="border-t border-[var(--color-border)]">
                        <td className="p-3 align-top w-[55%]">
                          <div className={`font-medium ${hasPermission ? "text-[var(--color-foreground)]" : "text-[var(--color-muted)] opacity-70"}`}>{kb.name}</div>
                        </td>
                        <td className="p-3 align-middle text-center">
                          {isImplicitKnowledgeManager ? (
                            <input type="checkbox" checked readOnly tabIndex={-1} className="w-4 h-4 border-[var(--color-border)] bg-[var(--color-border)] cursor-default" />
                          ) : (
                            <input
                              type="checkbox"
                              checked={hasPermission}
                              onChange={(e) =>
                                setPermissionForUser(kb.uuid, e.target.checked ? (user.role === "user" ? PERM_USE : PERM_TRAIN) : PERM_NONE)
                              }
                              className="kb-perm-checkbox focus:ring-0 focus:outline-none focus:shadow-none [&:focus]:outline-none [&:focus]:ring-0 [&:focus]:shadow-none"
                            />
                          )}
                        </td>
                        <td className="p-3 align-middle text-center">
                          {isImplicitKnowledgeManager ? (
                            <input type="checkbox" checked readOnly tabIndex={-1} className="w-4 h-4 border-[var(--color-border)] bg-[var(--color-border)] cursor-default" />
                          ) : (
                            <input
                              type="checkbox"
                              checked={canTrain}
                              disabled={!hasPermission}
                              onChange={(e) =>
                                setPermissionForUser(kb.uuid, e.target.checked ? PERM_TRAIN : PERM_USE)
                              }
                              className="kb-perm-checkbox focus:ring-0 focus:outline-none focus:shadow-none [&:focus]:outline-none [&:focus]:ring-0 [&:focus]:shadow-none"
                            />
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <ModalFooter className="mt-4">
              <Button
                type="button"
                onClick={onClose}
                variant="secondary"
                disabled={actionLoading}
              >
                {t("common.cancel")}
              </Button>
              <Button
                type="button"
                onClick={handleSave}
                disabled={actionLoading || changedKbUuids.length === 0}
              >
                {setPermissionsMutation.isPending ? t("common.loading") : t("kb.savePermissions")}
              </Button>
            </ModalFooter>
          </>
        )}
    </Modal>
  );
}
