import { useEffect, useMemo, useState } from "react";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import {
  clearPlatformAdminDebugDate,
  fetchPlatformAdminDebugDate,
  updatePlatformAdminDebugDate,
} from "../api";
import PlatformAdminLayout from "./PlatformAdminLayout";

export default function PlatformAdminDateSimulationPage() {
  const [debugDate, setDebugDate] = useState("");
  const [currentDate, setCurrentDate] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fallbackCurrentDate = useMemo(() => new Date().toISOString().slice(0, 10), []);

  const loadDebugDate = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchPlatformAdminDebugDate();
      setDebugDate(result.simulated_date ?? "");
      setCurrentDate(result.current_date ?? "");
    } catch (err) {
      setError(getApiErrorMessage(err) ?? "Nem sikerült betölteni a dátum szimulációt.");
      setCurrentDate(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDebugDate();
  }, []);

  const saveDebugDate = async () => {
    setSaving(true);
    setError(null);
    try {
      const result = await updatePlatformAdminDebugDate(debugDate || null);
      setDebugDate(result.simulated_date ?? "");
      setCurrentDate(result.current_date ?? "");
    } catch (err) {
      setError(getApiErrorMessage(err) ?? "Nem sikerült menteni a szimulált dátumot.");
    } finally {
      setSaving(false);
    }
  };

  const clearDebugDate = async () => {
    setSaving(true);
    setError(null);
    try {
      const result = await clearPlatformAdminDebugDate();
      setDebugDate("");
      setCurrentDate(result.current_date ?? "");
    } catch (err) {
      setError(getApiErrorMessage(err) ?? "Nem sikerült törölni a szimulált dátumot.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <PlatformAdminLayout>
      <div className="mx-auto max-w-3xl space-y-6">
        <PageHeader
          eyebrow="Platform admin"
          title="Dátum szimuláció"
          description="A beállított dátum globálisan érvényes a számlázási időszakokra és minden tenant használati számítására."
        />

        {error ? <Alert tone="error">{error}</Alert> : null}

        <section className="app-surface p-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-sm font-medium text-[var(--color-muted)]">Aktuális rendszer dátum</p>
              <p className="mt-1 text-2xl font-semibold text-[var(--color-foreground)]">
                {loading ? "..." : currentDate || fallbackCurrentDate}
              </p>
              <p className="mt-2 text-sm text-[var(--color-muted)]">
                Üres dátummal a rendszer visszaáll a valós mai napra.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="date"
                value={debugDate}
                onChange={(event) => setDebugDate(event.target.value)}
                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm text-[var(--color-foreground)]"
              />
              <Button type="button" size="sm" onClick={saveDebugDate} disabled={saving || loading}>
                {saving ? "Mentés..." : "Dátum alkalmazása"}
              </Button>
              <Button type="button" size="sm" variant="secondary" onClick={clearDebugDate} disabled={saving || loading}>
                Visszaállítás
              </Button>
            </div>
          </div>
        </section>
      </div>
    </PlatformAdminLayout>
  );
}
