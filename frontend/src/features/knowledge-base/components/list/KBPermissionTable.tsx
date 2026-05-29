import { PERM_NONE, PERM_TRAIN, PERM_USE, type KbPermissionRow } from "./kbListUtils";

type KBPermissionTableProps = {
  users: KbPermissionRow[];
  currentUserId?: number;
  t: (key: string) => string;
  onChange: (userId: number, permission: string) => void;
  mode: "create" | "settings";
};

export default function KBPermissionTable({ users, currentUserId, t, onChange, mode }: KBPermissionTableProps) {
  return (
    <div className={`border border-[var(--color-border)] rounded overflow-hidden ${mode === "create" ? "max-h-48" : "max-h-64"} overflow-y-auto`}>
      <table className="w-full text-sm">
        <tbody>
          <tr className="border-b border-[var(--color-border)] bg-[#efefef]">
            <td className="p-2 text-xs text-[var(--color-foreground)] font-normal w-[28%]">{t("roles.tableName")}</td>
            <td className="p-2 text-xs text-[var(--color-foreground)] font-normal w-[24%]">{t("roles.tableRole")}</td>
            <td className="p-2 text-xs text-[var(--color-foreground)] font-normal text-center w-[20%]">{t("kb.hasAccess")}</td>
            <td className="p-2 text-xs text-[var(--color-foreground)] font-normal text-center">{t("kb.columnTrainer")}</td>
          </tr>
          {users.map((user) => (
            <SettingsPermissionRow key={user.id} user={user} currentUserId={currentUserId} t={t} onChange={onChange} mode={mode} />
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
  mode,
}: {
  user: KbPermissionRow;
  currentUserId?: number;
  t: (key: string) => string;
  onChange: (userId: number, permission: string) => void;
  mode: "create" | "settings";
}) {
  const isSelf = user.id === currentUserId;
  const perm = user.permission;
  const hasPermission = perm === PERM_USE || perm === PERM_TRAIN;
  const canTrain = perm === PERM_TRAIN;
  const isImplicitKnowledgeManager = user.role === "owner" || user.role === "admin";
  const roleLabel = user.role === "owner" ? t("roles.roleOwner") : user.role === "admin" ? t("roles.roleAdmin") : t("roles.roleUser");
  const nameRoleColor = isImplicitKnowledgeManager ? "text-[var(--color-muted)]" : hasPermission ? "text-[var(--color-foreground)]" : "text-[var(--color-muted)] opacity-70";

  return (
    <tr className="border-t border-[var(--color-border)]">
      <td className="p-3 align-top w-[28%]">
        <div className={`font-medium ${nameRoleColor}`}>{user.name ?? "—"}</div>
      </td>
      <td className="p-3 align-top w-[24%]">
        <div className={`font-medium ${nameRoleColor}`}>{roleLabel}</div>
      </td>
      <td className="p-3 align-middle text-center w-[20%]">
        {isSelf || (mode === "settings" && isImplicitKnowledgeManager) ? (
          <input type="checkbox" checked readOnly tabIndex={-1} className="w-4 h-4 border-[var(--color-border)] bg-[var(--color-border)] cursor-default" />
        ) : (
          <input
            type="checkbox"
            checked={hasPermission}
            onChange={(event) => onChange(user.id, event.target.checked ? PERM_USE : PERM_NONE)}
            className="kb-perm-checkbox focus:ring-0 focus:outline-none focus:shadow-none [&:focus]:outline-none [&:focus]:ring-0 [&:focus]:shadow-none"
          />
        )}
      </td>
      <td className="p-3 align-middle text-center">
        {mode === "settings" && isImplicitKnowledgeManager ? (
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
