import { PERM_NONE, PERM_TRAIN, PERM_USE, type KbPermissionRow } from "./kbListUtils";

type KBPermissionTableProps = {
  users: KbPermissionRow[];
  currentUserId?: number;
  t: (key: string) => string;
  onChange: (userId: number, permission: string) => void;
  onBulkChange?: (enabled: boolean) => void;
  mode: "create" | "settings";
};

export default function KBPermissionTable({ users, currentUserId, t, onChange, onBulkChange, mode }: KBPermissionTableProps) {
  if (mode === "create") {
    return (
      <div className="border border-[var(--color-border)] rounded overflow-hidden max-h-48 overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#efefef]">
            <tr>
              <th className="p-2 text-left text-xs font-normal text-[var(--color-foreground)]">{t("roles.tableName")}</th>
              <th className="p-2 text-left text-xs font-normal text-[var(--color-foreground)]">{t("roles.tableEmail")}</th>
              <th className="p-2 text-left text-xs font-normal text-[var(--color-foreground)]">{t("kb.tableActions")}</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id} className="border-t border-[var(--color-border)]">
                <td className="p-2 text-[var(--color-foreground)]">{user.name ?? "—"}</td>
                <td className="p-2 text-[var(--color-muted)]">{user.email}</td>
                <td className="p-2">
                  <select
                    value={user.permission === PERM_NONE && user.id === currentUserId ? PERM_TRAIN : user.permission}
                    onChange={(event) => onChange(user.id, event.target.value)}
                    className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-1.5 rounded text-sm"
                  >
                    {user.id !== currentUserId ? <option value={PERM_NONE}>{t("kb.permissionNone")}</option> : null}
                    <option value={PERM_USE}>{t("kb.permissionUse")}</option>
                    <option value={PERM_TRAIN}>{t("kb.permissionTrain")}</option>
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  const allEnabled = users.filter((user) => user.id !== currentUserId).every((user) => user.permission === PERM_USE || user.permission === PERM_TRAIN);
  return (
    <div className="border border-[var(--color-border)] rounded overflow-hidden max-h-64 overflow-y-auto">
      <table className="w-full text-sm">
        <tbody>
          <tr className="border-b border-[var(--color-border)] bg-[#efefef]">
            <td className="p-2 w-[20px] align-middle">
              <input
                type="checkbox"
                checked={allEnabled}
                onChange={(event) => onBulkChange?.(event.target.checked)}
                className="kb-perm-checkbox focus:ring-0 focus:outline-none focus:shadow-none [&:focus]:outline-none [&:focus]:ring-0 [&:focus]:shadow-none"
                aria-label={t("kb.everyone")}
              />
            </td>
            <td className="p-2 text-xs text-[var(--color-foreground)] font-normal w-[30%]">{t("roles.tableName")}</td>
            <td className="p-2 text-xs text-[var(--color-foreground)] font-normal w-[30%]">{t("roles.tableRole")}</td>
            <td className="p-2 text-xs text-[var(--color-foreground)] font-normal text-center">{t("kb.columnTrainer")}</td>
          </tr>
          {users.map((user) => (
            <SettingsPermissionRow key={user.id} user={user} currentUserId={currentUserId} t={t} onChange={onChange} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SettingsPermissionRow({
  user,
  currentUserId,
  t,
  onChange,
}: {
  user: KbPermissionRow;
  currentUserId?: number;
  t: (key: string) => string;
  onChange: (userId: number, permission: string) => void;
}) {
  const isSelf = user.id === currentUserId;
  const perm = user.permission;
  const hasPermission = perm === PERM_USE || perm === PERM_TRAIN;
  const canTrain = perm === PERM_TRAIN;
  const isOwnerRow = user.role === "owner";
  const roleLabel = user.role === "owner" ? t("roles.roleOwner") : user.role === "admin" ? t("roles.roleAdmin") : t("roles.roleUser");
  const nameRoleColor = isOwnerRow ? "text-[var(--color-muted)]" : hasPermission ? "text-[var(--color-foreground)]" : "text-[var(--color-muted)] opacity-70";

  return (
    <tr className="border-t border-[var(--color-border)]">
      <td className="p-2 w-[20px] align-middle">
        {isSelf || isOwnerRow ? (
          <input type="checkbox" checked readOnly tabIndex={-1} className="w-4 h-4 border-[var(--color-border)] bg-[var(--color-border)] cursor-default" />
        ) : (
          <input
            type="checkbox"
            checked={hasPermission}
            onChange={(event) => onChange(user.id, event.target.checked ? (user.role === "user" ? PERM_USE : PERM_TRAIN) : PERM_NONE)}
            className="kb-perm-checkbox focus:ring-0 focus:outline-none focus:shadow-none [&:focus]:outline-none [&:focus]:ring-0 [&:focus]:shadow-none"
          />
        )}
      </td>
      <td className="p-3 align-top w-[30%]">
        <div className={`font-medium ${nameRoleColor}`}>{user.name ?? "—"}</div>
      </td>
      <td className="p-3 align-top w-[30%]">
        <div className={`font-medium ${nameRoleColor}`}>{roleLabel}</div>
      </td>
      <td className="p-3 align-middle text-center">
        {isOwnerRow || (user.role === "admin" && (isSelf || canTrain)) ? (
          <input type="checkbox" checked readOnly tabIndex={-1} className="w-4 h-4 border-[var(--color-border)] bg-[var(--color-border)] cursor-default" />
        ) : isSelf && user.role === "user" ? (
          <span className="text-[var(--color-muted)]">{canTrain ? t("kb.permissionTrain") : perm === PERM_USE ? t("kb.permissionUse") : "—"}</span>
        ) : (
          <input
            type="checkbox"
            checked={canTrain}
            disabled={!hasPermission}
            onChange={(event) => onChange(user.id, event.target.checked ? PERM_TRAIN : PERM_USE)}
            className="kb-perm-checkbox focus:ring-0 focus:outline-none focus:shadow-none [&:focus]:outline-none [&:focus]:ring-0 [&:focus]:shadow-none"
          />
        )}
      </td>
    </tr>
  );
}
