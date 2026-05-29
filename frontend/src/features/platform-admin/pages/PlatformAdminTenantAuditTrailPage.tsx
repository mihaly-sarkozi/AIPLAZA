import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { formatDateTime } from "../../../utils/dateTimeFormatting";
import {
  exportPlatformAdminTenantAuditTrail,
  fetchActivePlatformTenants,
  fetchPlatformAdminTenantAuditTrail,
} from "../api";
import { usePlatformAdminStore } from "../state";
import type { PlatformAdminAuditTrailItem, PlatformAdminTenant } from "../types";
import PlatformAdminLayout from "./PlatformAdminLayout";

const PAGE_SIZE = 50;

const AUDIT_ACTION_FILTERS = [
  {
    id: "login_logout",
    label: "Belépés / kilépés",
    actions: [
      "login_success",
      "login_failed",
      "login_2fa_required",
      "login_2fa_failed",
      "login_2fa_rate_limited",
      "login_2fa_success",
      "logout",
      "logout_failed",
      "logout_error",
      "platform_admin_login_success",
      "platform_admin_login_failed",
      "platform_admin_logout",
    ],
  },
  {
    id: "registration",
    label: "Regisztráció / meghívó",
    actions: [
      "password_set_by_invite",
      "email_confirmed",
      "forgot_password_link_sent",
      "invite_resent",
      "password_changed",
      "user_created",
    ],
  },
  {
    id: "session",
    label: "Session frissítés",
    actions: ["refresh", "refresh_failed", "platform_admin_refresh", "platform_admin_refresh_failed"],
  },
  {
    id: "user_changes",
    label: "User módosítás",
    actions: ["user_updated", "user_email_changed", "user_role_changed"],
  },
  {
    id: "user_create",
    label: "User létrehozás",
    actions: ["user_created"],
  },
  {
    id: "user_delete",
    label: "User törlés",
    actions: ["user_deleted"],
  },
  {
    id: "knowledge",
    label: "Tudástár események",
    actions: ["knowledge_created", "knowledge_deleted", "knowledge_permission_changed", "knowledge_setting_changed"],
  },
  {
    id: "platform_admin",
    label: "Platform admin",
    actions: [
      "platform_admin_login_success",
      "platform_admin_login_failed",
      "platform_admin_mfa_required",
      "platform_admin_mfa_passed",
      "platform_admin_mfa_failed",
      "platform_admin_profile_updated",
      "platform_admin_password_changed",
      "platform_admin_stats_viewed",
      "platform_admin_tenant_stats_viewed",
      "platform_admin_security_ip_banned",
      "platform_admin_security_ip_unbanned",
      "platform_admin_security_alert_ack",
    ],
  },
] as const;

const ALL_AUDIT_ACTION_GROUP_IDS = AUDIT_ACTION_FILTERS.map((group) => group.id);

function tenantSlugFromHost(): string | null {
  const host = window.location.hostname.toLowerCase();
  const parts = host.split(".");
  if (parts.length < 3) return null;
  const slug = parts[0];
  return slug && slug !== "www" ? slug : null;
}

function formatTimestamp(value: string, timezone?: string | null): string {
  const normalized = /Z$|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`;
  return formatDateTime(normalized, {
    locale: "hu",
    timezone: timezone || "UTC",
    dateFormat: "YYYY-MM-DD",
    timeFormat: "HH:mm:ss",
  });
}

function maskedEmail(item: PlatformAdminAuditTrailItem): string {
  return item.target_user_email_masked || item.actor_email_masked || "-";
}

function actorLabel(item: PlatformAdminAuditTrailItem): string {
  const actorName = item.actor_name || item.actor_type || "ismeretlen";
  const actorEmail = item.actor_email_masked ? `, ${item.actor_email_masked}` : "";
  const actorId = item.actor_user_id ? `user #${item.actor_user_id}` : item.user_id ? `user #${item.user_id}` : null;
  return actorId ? `${actorName} (${actorId}${actorEmail})` : `${actorName}${actorEmail}`;
}

const CHANGE_FIELD_LABELS: Record<string, string> = {
  name: "Név",
  is_active: "Aktív állapot",
  role: "Szerepkör",
  email: "Email cím",
  public_enabled: "Publikus hozzáférés",
  pii_depersonalization_enabled: "PII deperszonalizáció",
  two_factor_enabled: "Kétlépcsős azonosítás",
  old_permission: "Jogosultság",
  permission: "Jogosultság",
};

function fieldLabel(key: string): string {
  return CHANGE_FIELD_LABELS[key] || key.replaceAll("_", " ");
}

function formatChangeValue(value: unknown, key?: string): string {
  if (typeof value === "boolean") {
    if (key === "is_active") return value ? "aktív" : "inaktív";
    return value ? "bekapcsolva" : "kikapcsolva";
  }
  if (key === "old_permission" || key === "new_permission" || key === "permission") {
    return permissionLabel(value);
  }
  if (value === null || value === undefined || value === "") return "-";
  return String(value);
}

function permissionLabel(value: unknown): string {
  const permission = String(value || "none").trim().toLowerCase();
  if (permission === "train") return "használat és tanítás";
  if (permission === "use") return "használat";
  if (permission === "none") return "nincs jogosultság";
  return String(value || "-");
}

function permissionCapabilities(value: unknown): string[] {
  const permission = String(value || "none").trim().toLowerCase();
  if (permission === "train") return ["használat", "tanítás"];
  if (permission === "use") return ["használat"];
  return [];
}

function auditKnowledgeBaseLabel(details: Record<string, unknown>): string {
  const name = typeof details.kb_name === "string" ? details.kb_name.trim() : "";
  const uuid = typeof details.kb_uuid === "string" ? details.kb_uuid.trim() : "";
  return name || uuid || "ismeretlen tudástár";
}

function permissionChangeDescriptions(details: Record<string, unknown>): string[] {
  const oldPermission = details.old_permission;
  const newPermission = details.new_permission;
  const oldCapabilities = new Set(permissionCapabilities(oldPermission));
  const newCapabilities = new Set(permissionCapabilities(newPermission));
  const added = [...newCapabilities].filter((item) => !oldCapabilities.has(item));
  const removed = [...oldCapabilities].filter((item) => !newCapabilities.has(item));
  const changes: string[] = [];
  if (added.length) changes.push(`Kapott jog: ${added.join(", ")}`);
  if (removed.length) changes.push(`Kikapcsolt jog: ${removed.join(", ")}`);
  return changes;
}

function normalizedComparableValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value).trim();
}

function changeDescriptions(item: PlatformAdminAuditTrailItem): string[] {
  const details = item.details || {};
  if (item.action === "knowledge_setting_changed") {
    const field = typeof details.field === "string" ? details.field : "érték";
    if (normalizedComparableValue(details.old_value) === normalizedComparableValue(details.new_value)) return [];
    return [`${fieldLabel(field)}: ${formatChangeValue(details.old_value, field)} -> ${formatChangeValue(details.new_value, field)}`];
  }
  const oldValues = details.old_values && typeof details.old_values === "object" ? (details.old_values as Record<string, unknown>) : {};
  const newValues = details.new_values && typeof details.new_values === "object" ? (details.new_values as Record<string, unknown>) : {};
  const keys = Array.from(new Set([...Object.keys(oldValues), ...Object.keys(newValues)]));
  if (keys.length) {
    return keys
      .map((key) => {
        const oldValue = oldValues[key];
        const newValue = key in newValues ? newValues[key] : details[key];
        if (normalizedComparableValue(oldValue) === normalizedComparableValue(newValue)) return null;
        return `${fieldLabel(key)} megváltozott: ${formatChangeValue(oldValue, key)} -> ${formatChangeValue(newValue, key)}`;
      })
      .filter((change): change is string => Boolean(change));
  }
  if ("old_value" in details || "new_value" in details) {
    const key = item.action === "user_role_changed" ? "role" : item.action === "user_email_changed" ? "email" : "érték";
    if (normalizedComparableValue(details.old_value) === normalizedComparableValue(details.new_value)) return [];
    return [`${fieldLabel(key)} megváltozott: ${formatChangeValue(details.old_value, key)} -> ${formatChangeValue(details.new_value, key)}`];
  }
  if ("old_permission" in details || "new_permission" in details) {
    if (normalizedComparableValue(details.old_permission) === normalizedComparableValue(details.new_permission)) return [];
    const permissionChanges = permissionChangeDescriptions(details);
    return permissionChanges.length
      ? permissionChanges
      : [
          `Jogosultság megváltozott: ${formatChangeValue(
            details.old_permission,
            "old_permission",
          )} -> ${formatChangeValue(details.new_permission, "new_permission")}`,
        ];
  }
  return [];
}

function auditListTitle(item: PlatformAdminAuditTrailItem): string {
  if (item.action !== "knowledge_permission_changed" && item.action !== "knowledge_setting_changed") return item.title;
  const kbName = auditKnowledgeBaseLabel(item.details || {});
  return kbName && kbName !== "ismeretlen tudástár" ? `${item.title} - ${kbName}` : item.title;
}

function AuditEventCard({ item, timezone }: { item: PlatformAdminAuditTrailItem; timezone?: string | null }) {
  const [open, setOpen] = useState(false);
  const changes = changeDescriptions(item);
  const knowledgeBaseName =
    item.action === "knowledge_permission_changed" || item.action === "knowledge_setting_changed"
      ? auditKnowledgeBaseLabel(item.details || {})
      : null;
  return (
    <article className="border-b border-[var(--color-border)] px-4 py-3 last:border-b-0">
      <div className="grid gap-3 text-sm md:grid-cols-[80px_180px_minmax(0,1fr)_90px_220px_auto] md:items-center">
        <div className="font-mono text-xs font-semibold text-[var(--color-muted)]">#{item.id}</div>
        <time className="font-medium text-[var(--color-muted)]">{formatTimestamp(item.created_at, timezone)}</time>
        <div className="min-w-0">
          <div className="truncate font-medium text-[var(--color-foreground)]">{auditListTitle(item)}</div>
        </div>
        <div className="text-[var(--color-muted)]">#{item.user_id ?? "-"}</div>
        <div className="truncate font-mono text-xs text-[var(--color-muted)]" title={maskedEmail(item)}>
          {maskedEmail(item)}
        </div>
        <Button type="button" size="sm" variant="secondary" onClick={() => setOpen((value) => !value)}>
          {open ? "Bezárás" : "Részletek"}
        </Button>
      </div>

      {open ? (
        <div className="mt-3 rounded-lg border border-[var(--color-border)]/70 bg-[var(--color-background)] px-3 py-3 text-sm">
          <div className="grid gap-2 md:grid-cols-2">
            <div>
              <span className="font-medium text-[var(--color-foreground)]">Ki csinálta:</span>{" "}
              <span className="text-[var(--color-muted)]">{actorLabel(item)}</span>
            </div>
            <div>
              <span className="font-medium text-[var(--color-foreground)]">Esemény azonosító:</span>{" "}
              <span className="text-[var(--color-muted)]">{item.action}</span>
              <span className="mx-3 text-[var(--color-muted)]">|</span>
              <span className="font-medium text-[var(--color-foreground)]">IP:</span>{" "}
              <span className="text-[var(--color-muted)]">{item.ip || "-"}</span>
            </div>
            <div className="md:col-span-2">
              <span className="font-medium text-[var(--color-foreground)]">User-agent:</span>{" "}
              <span className="break-words text-[var(--color-muted)]">{item.user_agent || "-"}</span>
            </div>
            {knowledgeBaseName ? (
              <div className="md:col-span-2">
                <span className="font-medium text-[var(--color-foreground)]">Tudástár neve:</span>{" "}
                <span className="text-[var(--color-muted)]">{knowledgeBaseName}</span>
              </div>
            ) : null}
          </div>
          {changes.length ? (
            <div className="mt-3 border-t border-[var(--color-border)] pt-3">
              <div className="text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">Változás</div>
              <ul className="mt-2 space-y-1 text-[var(--color-foreground)]">
                {changes.map((change) => (
                  <li key={change}>{change}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

export default function PlatformAdminTenantAuditTrailPage() {
  const [tenants, setTenants] = useState<PlatformAdminTenant[]>([]);
  const [tenantId, setTenantId] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [emailSearch, setEmailSearch] = useState("");
  const [selectedActionGroups, setSelectedActionGroups] = useState<string[]>(ALL_AUDIT_ACTION_GROUP_IDS);
  const [appliedFromDate, setAppliedFromDate] = useState("");
  const [appliedToDate, setAppliedToDate] = useState("");
  const [appliedEmailSearch, setAppliedEmailSearch] = useState("");
  const [appliedActionGroups, setAppliedActionGroups] = useState<string[]>(ALL_AUDIT_ACTION_GROUP_IDS);
  const [filterRunId, setFilterRunId] = useState(0);
  const [items, setItems] = useState<PlatformAdminAuditTrailItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [auditTimezone, setAuditTimezone] = useState("UTC");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const loadingMoreRef = useRef(false);
  const { user, loadingUser } = usePlatformAdminStore();
  const authReady = !loadingUser && Boolean(user);
  const selectedTenantId = useMemo(() => Number(tenantId || 0), [tenantId]);
  const appliedActions = useMemo(() => {
    if (!appliedActionGroups.length) return [];
    const actions = AUDIT_ACTION_FILTERS
      .filter((group) => appliedActionGroups.includes(group.id))
      .flatMap((group) => [...group.actions]);
    return Array.from(new Set(actions));
  }, [appliedActionGroups]);

  useEffect(() => {
    if (!authReady) return;
    let cancelled = false;
    setLoading(true);
    fetchActivePlatformTenants()
      .then((result) => {
        if (cancelled) return;
        setTenants(result);
        const hostSlug = tenantSlugFromHost();
        const hostTenant = hostSlug ? result.find((tenant) => tenant.slug === hostSlug) : null;
        const defaultTenant = hostTenant || result[0];
        if (defaultTenant) setTenantId(String(defaultTenant.id));
      })
      .catch((err) => {
        if (!cancelled) setError(getApiErrorMessage(err) ?? "Nem sikerült betölteni a tenantokat.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [authReady]);

  const loadAudit = useCallback(
    async ({ append, cursor }: { append: boolean; cursor?: string | null }) => {
      if (!authReady || !selectedTenantId) return;
      if (!appliedActionGroups.length) {
        setItems([]);
        setNextCursor(null);
        setLoading(false);
        setLoadingMore(false);
        return;
      }
      if (append) {
        loadingMoreRef.current = true;
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      setError(null);
      try {
        const result = await fetchPlatformAdminTenantAuditTrail({
          tenantId: selectedTenantId,
          fromDate: appliedFromDate,
          toDate: appliedToDate,
          email: appliedEmailSearch,
          actions: appliedActions,
          limit: PAGE_SIZE,
          cursor,
        });
        setAuditTimezone(result.tenant.timezone || "UTC");
        setItems((current) => (append ? [...current, ...result.items] : result.items));
        setNextCursor(result.next_cursor ?? null);
      } catch (err) {
        setError(getApiErrorMessage(err) ?? "Nem sikerült betölteni az audit naplót.");
      } finally {
        if (append) {
          loadingMoreRef.current = false;
          setLoadingMore(false);
        } else {
          setLoading(false);
        }
      }
    },
    [appliedActionGroups.length, appliedActions, appliedEmailSearch, appliedFromDate, appliedToDate, authReady, selectedTenantId]
  );

  useEffect(() => {
    if (!authReady || !selectedTenantId) return;
    void loadAudit({ append: false });
  }, [authReady, filterRunId, loadAudit, selectedTenantId]);

  useEffect(() => {
    const node = sentinelRef.current;
    if (!node || !nextCursor) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries[0]?.isIntersecting && nextCursor && !loadingMoreRef.current) {
        void loadAudit({ append: true, cursor: nextCursor });
      }
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [loadAudit, nextCursor]);

  const exportCsv = async () => {
    if (!selectedTenantId || !appliedActionGroups.length) return;
    setExporting(true);
    setError(null);
    try {
      await exportPlatformAdminTenantAuditTrail({
        tenantId: selectedTenantId,
        fromDate: appliedFromDate,
        toDate: appliedToDate,
        email: appliedEmailSearch,
        actions: appliedActions,
      });
    } catch (err) {
      setError(getApiErrorMessage(err) ?? "Nem sikerült exportálni az audit naplót.");
    } finally {
      setExporting(false);
    }
  };

  const applyFilters = () => {
    setAppliedFromDate(fromDate);
    setAppliedToDate(toDate);
    setAppliedEmailSearch(emailSearch.trim());
    setAppliedActionGroups(selectedActionGroups);
    setFilterRunId((value) => value + 1);
  };

  const selectedTenant = tenants.find((tenant) => String(tenant.id) === tenantId);

  return (
    <PlatformAdminLayout>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Platform admin"
          title="Audit napló"
          description="Tenantonkénti autentikációs, user-kezelési és tudástár jogosultsági események időrendben visszafelé."
        />

        {error ? <Alert tone="error">{error}</Alert> : null}
        {selectedTenant ? (
          <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-4 py-2 text-sm text-[var(--color-muted)]">
            Aktív tenant: <span className="font-semibold text-[var(--color-foreground)]">{selectedTenant.name} ({selectedTenant.slug})</span>
            <span className="ml-2">Időzóna: <span className="font-semibold text-[var(--color-foreground)]">{auditTimezone}</span></span>
          </div>
        ) : null}

        <section className="app-surface p-4">
          <div className="grid gap-3 md:grid-cols-[1.3fr_1fr_1fr_1.2fr_auto_auto] md:items-end">
            <label className="block">
              <span className="mb-1 block text-sm text-[var(--color-label)]">Tenant</span>
              <select
                value={tenantId}
                onChange={(event) => setTenantId(event.target.value)}
                className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm"
              >
                {tenants.map((tenant) => (
                  <option key={tenant.id} value={tenant.id}>
                    {tenant.name} ({tenant.slug})
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-sm text-[var(--color-label)]">Ettől</span>
              <input
                type="date"
                value={fromDate}
                onChange={(event) => setFromDate(event.target.value)}
                className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm text-[var(--color-label)]">Eddig</span>
              <input
                type="date"
                value={toDate}
                onChange={(event) => setToDate(event.target.value)}
                className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm text-[var(--color-label)]">Email keresés</span>
              <input
                type="email"
                value={emailSearch}
                onChange={(event) => setEmailSearch(event.target.value)}
                placeholder="nev@example.com"
                className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm"
              />
            </label>
            <Button type="button" variant="secondary" onClick={applyFilters} disabled={loading || !selectedTenantId}>
              Szűrés
            </Button>
            <Button type="button" onClick={exportCsv} disabled={exporting || !selectedTenantId}>
              {exporting ? "Export..." : "CSV export"}
            </Button>
          </div>
          <div className="mt-4 border-t border-[var(--color-border)] pt-4">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-medium text-[var(--color-label)]">Eseménytípus szűrés</p>
              <div className="flex flex-wrap gap-2">
                <Button type="button" size="sm" variant="secondary" onClick={() => setSelectedActionGroups(ALL_AUDIT_ACTION_GROUP_IDS)}>
                  Mindent bekapcsol
                </Button>
                <Button type="button" size="sm" variant="secondary" onClick={() => setSelectedActionGroups([])}>
                  Mindent töröl
                </Button>
              </div>
            </div>
            <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
              {AUDIT_ACTION_FILTERS.map((group) => {
                const checked = selectedActionGroups.includes(group.id);
                const checkboxId = `audit-action-filter-${group.id}`;
                return (
                  <div key={group.id} className="flex items-center px-1 py-1 text-sm text-[var(--color-muted)]">
                    <input
                      id={checkboxId}
                      type="checkbox"
                      checked={checked}
                      onChange={(event) => {
                        setSelectedActionGroups((current) => {
                          if (event.target.checked) return [...current, group.id];
                          return current.filter((id) => id !== group.id);
                        });
                      }}
                      className="kb-perm-checkbox focus:ring-0 focus:outline-none focus:shadow-none [&:focus]:outline-none [&:focus]:ring-0 [&:focus]:shadow-none"
                    />
                    <label htmlFor={checkboxId} className="!mb-0 ml-2 !block translate-y-px cursor-pointer !font-medium leading-4 !text-[var(--color-muted)]">
                      {group.label}
                    </label>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {loading ? (
          <div className="app-surface p-6 text-center text-[var(--color-muted)]">Audit napló betöltése...</div>
        ) : items.length ? (
          <div>
            <div className="overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-card)]">
              <div className="hidden grid-cols-[80px_180px_minmax(0,1fr)_90px_220px_auto] gap-3 border-b border-[var(--color-border)] px-4 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)] md:grid">
                <div>ID</div>
                <div>Timestamp</div>
                <div>Szöveg</div>
                <div>User ID</div>
                <div>Email</div>
                <div></div>
              </div>
              {items.map((item) => (
                <AuditEventCard key={item.id} item={item} timezone={auditTimezone} />
              ))}
            </div>
            {nextCursor ? (
              <div ref={sentinelRef} className="py-6 text-center text-sm text-[var(--color-muted)]">
                {loadingMore ? "További események betöltése..." : "Görgess tovább a régebbi eseményekhez"}
              </div>
            ) : (
              <div className="py-6 text-center text-sm text-[var(--color-muted)]">Nincs több esemény.</div>
            )}
          </div>
        ) : (
          <div className="app-surface p-6 text-center text-[var(--color-muted)]">
            Nincs audit esemény a kiválasztott szűrőkkel.
          </div>
        )}
      </div>
    </PlatformAdminLayout>
  );
}
