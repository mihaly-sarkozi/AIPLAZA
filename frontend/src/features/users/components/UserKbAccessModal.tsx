import { useEffect, useState } from "react";
import { useQueries } from "@tanstack/react-query";
import { useTranslation } from "../../../i18n";
import { getKbPermissions } from "../../knowledge-base/services";
import { queryKeys } from "../../../queryKeys";
import { useSetKbPermissionsMutation } from "../../knowledge-base/hooks/useKb";
import type { KbItem, KbPermissionItem } from "../../knowledge-base/services";
import type { UserListItem } from "../hooks/useUsers";

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

  const permissionQueries = useQueries({
    queries: kbList.map((kb) => ({
      queryKey: [...queryKeys.kb, kb.uuid, "permissions"],
      queryFn: () => getKbPermissions(kb.uuid),
      enabled: !!user?.id && !!kb.uuid,
    })),
  });

  const setPermissionsMutation = useSetKbPermissionsMutation();
  const actionLoading = setPermissionsMutation.isPending;

  const allLoaded = permissionQueries.every((q) => !q.isLoading && q.data != null);
  const isLoading = permissionQueries.some((q) => q.isLoading);

  useEffect(() => {
    if (!allLoaded || !user?.id) return;
    const next: Record<string, Array<{ user_id: number; permission: string }>> = {};
    permissionQueries.forEach((q, i) => {
      const kb = kbList[i];
      if (!kb || !q.data) return;
      next[kb.uuid] = (q.data as KbPermissionItem[]).map((p) => ({ user_id: p.user_id, permission: p.permission }));
    });
    setPermissionsByKb(next);
  }, [allLoaded, user?.id, kbList, permissionQueries.map((q) => q.dataUpdatedAt).join(",")]);

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

  const handleSave = () => {
    kbList.forEach((kb) => {
      const list = permissionsByKb[kb.uuid];
      if (list) setPermissionsMutation.mutate({ uuid: kb.uuid, permissions: list });
    });
    onClose();
  };

  const isOwnerRow = user.role === "owner";

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-6 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-lg">
        <p className="text-sm text-[var(--color-muted)] mb-0.5">{t("nav.knowledgeBase")}</p>
        <h2 className="text-2xl font-bold mb-1 text-[var(--color-foreground)]">
          {user.name ?? user.email}
        </h2>
        <p className="text-sm text-[var(--color-muted)] mb-4">{t("roles.kbAccessHint")}</p>
        {isLoading ? (
          <p className="text-[var(--color-muted)]">{t("common.loading")}</p>
        ) : (
          <>
            <div className="border border-[var(--color-border)] rounded overflow-hidden max-h-64 overflow-y-auto">
              <table className="w-full text-sm">
                <tbody>
                  <tr className="border-b border-[var(--color-border)] bg-[var(--color-table-head)]">
                    <td className="p-2 w-[20px] align-middle" />
                    <td className="p-2 text-xs font-normal text-[var(--color-foreground)] w-[30%]">{t("kb.tableName")}</td>
                    <td className="p-2 text-xs font-normal text-[var(--color-foreground)] text-center">{t("kb.columnTrainer")}</td>
                  </tr>
                  {kbList.map((kb) => {
                    const perm = getPermissionForUser(kb.uuid);
                    const hasPermission = perm === PERM_USE || perm === PERM_TRAIN;
                    const canTrain = perm === PERM_TRAIN;
                    const isAdmin = user.role === "admin";

                    return (
                      <tr key={kb.uuid} className="border-t border-[var(--color-border)]">
                        <td className="p-2 w-[20px] align-middle">
                          {isOwnerRow ? (
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
                        <td className="p-3 align-top w-[30%]">
                          <div className={`font-medium ${hasPermission ? "text-[var(--color-foreground)]" : "text-[var(--color-muted)] opacity-70"}`}>{kb.name}</div>
                        </td>
                        <td className="p-3 align-middle text-center">
                          {isOwnerRow || (isAdmin && canTrain) ? (
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
            <div className="flex justify-end gap-2 mt-4">
              <button
                type="button"
                onClick={onClose}
                disabled={actionLoading}
                className="px-4 py-2 rounded text-[var(--color-foreground)] hover:bg-[var(--color-button-hover)] bg-[var(--color-card)] border border-[var(--color-border)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={actionLoading}
                className="px-4 py-2 rounded bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {setPermissionsMutation.isPending ? t("common.loading") : t("kb.savePermissions")}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
